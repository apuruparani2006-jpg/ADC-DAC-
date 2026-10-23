
import math
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent
BITS_OPTIONS = [4, 8, 10, 12, 16]

st.set_page_config(
    page_title="ADC and DAC Simulator with AI Tutor",
    page_icon="🔌",
    layout="wide"
)

st.title("ADC & DAC Visual Simulator")
st.caption(
    "Verilog simulation | Adjustable inputs | Waveform plots | AI Tutor"
)


# --------------------------------------------------
# VERILOG SIMULATION FUNCTIONS
# --------------------------------------------------

def simulate_verilog(mode, values, bits, vref_mv):
    """Compile and execute the corresponding Verilog testbench."""

    required_files = [
        ROOT / "adc.v",
        ROOT / "dac.v",
        ROOT / "tb_adc.v",
        ROOT / "tb_dac.v",
    ]

    missing = [p.name for p in required_files if not p.exists()]
    if missing:
        raise RuntimeError("Missing files: " + ", ".join(missing))

    compiler = shutil.which("iverilog")
    runner = shutil.which("vvp")

    if not compiler or not runner:
        raise RuntimeError(
            "Icarus Verilog is unavailable. Use the supplied Dockerfile "
            "or install Icarus Verilog."
        )

    if mode not in ("ADC", "DAC"):
        raise ValueError("Unknown simulation mode.")

    with tempfile.TemporaryDirectory(prefix="adc_dac_") as folder:
        work = Path(folder)

        if mode == "ADC":
            filenames = ["adc.v", "tb_adc.v"]
            input_filename = "adc_inputs.txt"
            top = "tb_adc"
            pattern = r"ADC_RESULT\s+(\d+)\s+(\d+)"
        else:
            filenames = ["dac.v", "tb_dac.v"]
            input_filename = "dac_inputs.txt"
            top = "tb_dac"
            pattern = r"DAC_RESULT\s+(\d+)\s+(\d+)"

        for filename in filenames:
            shutil.copy2(ROOT / filename, work / filename)

        (work / input_filename).write_text(
            "".join(f"{int(v)}\n" for v in values),
            encoding="utf-8"
        )

        compile_command = [
            compiler,
            "-g2012",
            "-s", top,
            f"-P{top}.BITS={bits}",
            f"-P{top}.VREF_MV={vref_mv}",
            "-o", "simulation.out",
            *filenames,
        ]

        compiled = subprocess.run(
            compile_command,
            cwd=work,
            capture_output=True,
            text=True,
            timeout=30,
        )

        if compiled.returncode != 0:
            raise RuntimeError(
                "Verilog compilation error:\n"
                + compiled.stdout + compiled.stderr
            )

        executed = subprocess.run(
            [runner, "simulation.out"],
            cwd=work,
            capture_output=True,
            text=True,
            timeout=30,
        )

        if executed.returncode != 0:
            raise RuntimeError(
                "Simulation error:\n"
                + executed.stdout + executed.stderr
            )

        matches = re.findall(pattern, executed.stdout)

        if len(matches) != len(values):
            raise RuntimeError(
                "Could not read every result from the Verilog simulation.\n"
                + executed.stdout
            )

        results = [(int(a), int(b)) for a, b in matches]
        return results, executed.stdout


# --------------------------------------------------
# WAVEFORM GENERATOR
# --------------------------------------------------

def generate_waveform(kind, minimum, maximum,
                      frequency, sampling_rate, cycles):

    duration = cycles / frequency
    sample_count = min(
        1000,
        max(2, int(duration * sampling_rate) + 1)
    )

    times = [i / sampling_rate for i in range(sample_count)]

    midpoint = (minimum + maximum) / 2
    amplitude = (maximum - minimum) / 2

    voltages = []

    for time in times:
        phase = (frequency * time) % 1.0

        if kind == "Sine":
            wave = math.sin(2 * math.pi * phase)

        elif kind == "Square":
            wave = 1.0 if phase < 0.5 else -1.0

        elif kind == "Triangle":
            wave = 1 - 4 * abs(phase - 0.5)

        else:  # Sawtooth
            wave = 2 * phase - 1

        voltages.append(midpoint + amplitude * wave)

    return times, voltages


def map_voltage_to_adc(voltage, minimum, maximum, vref_mv):
    """Map the selected input range into the ADC's 0-to-Vref range."""

    fraction = (voltage - minimum) / (maximum - minimum)
    fraction = max(0.0, min(1.0, fraction))

    return round(fraction * vref_mv)


def save_csv(rows, filename):
    data = pd.DataFrame(rows).to_csv(index=False).encode("utf-8")

    st.download_button(
        "Download CSV results",
        data,
        file_name=filename,
        mime="text/csv"
    )


# --------------------------------------------------
# ADC PAGE
# --------------------------------------------------

adc_tab, dac_tab, tutor_tab = st.tabs(
    ["ADC", "DAC", "AI Tutor"]
)

with adc_tab:
    st.header("ADC: Analog input to digital output")

    col1, col2 = st.columns(2)

    with col1:
        waveform = st.selectbox(
            "Waveform",
            ["Sine", "Square", "Triangle", "Sawtooth"]
        )

        minimum = st.number_input(
            "Minimum voltage (V)",
            value=0.0,
            min_value=-100.0,
            max_value=100.0,
            step=0.1
        )

        maximum = st.number_input(
            "Maximum voltage (V)",
            value=5.0,
            min_value=-100.0,
            max_value=100.0,
            step=0.1
        )

        frequency = st.number_input(
            "Signal frequency (Hz)",
            min_value=0.1,
            max_value=100000.0,
            value=100.0
        )

    with col2:
        sampling_rate = st.number_input(
            "Sampling frequency (samples/second)",
            min_value=1.0,
            max_value=1000000.0,
            value=1000.0
        )

        cycles = st.number_input(
            "Cycles to display",
            min_value=1,
            max_value=10,
            value=2
        )

        adc_bits = st.selectbox(
            "ADC resolution",
            BITS_OPTIONS,
            index=1,
            format_func=lambda b: f"{b} bits ({2**b} levels)"
        )

        adc_vref = st.number_input(
            "ADC reference voltage (V)",
            min_value=0.1,
            max_value=10.0,
            value=5.0,
            step=0.1
        )

    st.info(
        "The selected minimum and maximum voltages define the input "
        "waveform range. This simulator maps that range to 0–Vref "
        "before conversion, allowing negative input ranges as well."
    )

    if sampling_rate < 2 * frequency:
        st.warning(
            "Sampling frequency is below twice the signal frequency. "
            "The waveform may be undersampled."
        )

    if st.button("Run ADC", type="primary"):
        if maximum <= minimum:
            st.error("Maximum voltage must be greater than minimum voltage.")

        else:
            try:
                times, analog = generate_waveform(
                    waveform, minimum, maximum,
                    frequency, sampling_rate, cycles
                )

                vref_mv = round(adc_vref * 1000)

                adc_inputs = [
                    map_voltage_to_adc(v, minimum, maximum, vref_mv)
                    for v in analog
                ]

                result, raw_output = simulate_verilog(
                    "ADC", adc_inputs, adc_bits, vref_mv
                )

                codes = [code for _, code in result]
                max_code = (1 << adc_bits) - 1

                represented = [
                    minimum + code / max_code * (maximum - minimum)
                    for code in codes
                ]

                st.subheader("Analog input waveform")

                fig, ax = plt.subplots(figsize=(10, 4))
                ax.plot(times, analog, label="Analog input")
                ax.scatter(times, analog, s=12, label="Sample points")
                ax.set_xlabel("Time (seconds)")
                ax.set_ylabel("Voltage (V)")
                ax.set_title("ADC input")
                ax.grid(True, alpha=0.3)
                ax.legend()
                st.pyplot(fig)
                plt.close(fig)

                st.subheader("Digital output waveform")

                fig, ax = plt.subplots(figsize=(10, 4))
                ax.step(times, codes, where="post")
                ax.set_xlabel("Time (seconds)")
                ax.set_ylabel(f"Digital code (0–{max_code})")
                ax.set_title(f"{adc_bits}-bit ADC output")
                ax.grid(True, alpha=0.3)
                st.pyplot(fig)
                plt.close(fig)

                rows = []

                for i, (t, vin, code, vout) in enumerate(
                    zip(times, analog, codes, represented)
                ):
                    rows.append({
                        "Sample": i,
                        "Time_s": round(t, 8),
                        "Input_voltage_V": round(vin, 6),
                        "Digital_decimal": code,
                        "Digital_binary": format(
                            code, f"0{adc_bits}b"
                        ),
                        "Represented_voltage_V": round(vout, 6),
                    })

                st.subheader("Sample-by-sample results")
                st.dataframe(
                    pd.DataFrame(rows),
                    use_container_width=True,
                    hide_index=True
                )

                st.metric("Number of samples", len(codes))
                st.metric("Digital levels", 1 << adc_bits)
                st.metric(
                    "Voltage step across selected range",
                    f"{(maximum - minimum) / max_code:.6f} V"
                )

                save_csv(rows, "adc_results.csv")

                with st.expander("Raw Verilog simulation output"):
                    st.code(raw_output)

            except Exception as error:
                st.error(str(error))


# --------------------------------------------------
# DAC PAGE
# --------------------------------------------------

with dac_tab:
    st.header("DAC: Digital input to analog output")

    dac_bits = st.selectbox(
        "DAC resolution",
        BITS_OPTIONS,
        index=1,
        format_func=lambda b: f"{b} bits ({2**b} levels)"
    )

    dac_vref = st.number_input(
        "DAC reference voltage (V)",
        min_value=0.1,
        max_value=10.0,
        value=5.0,
        step=0.1
    )

    input_format = st.radio(
        "Digital input format",
        ["Decimal", "Binary"],
        horizontal=True
    )

    code_text = st.text_area(
        "Enter one code or a sequence separated by commas",
        value="0, 64, 128, 192, 255" if dac_bits == 8 else "0, 1, 2, 3",
        help="Example for 8 bits: 0, 64, 128, 192, 255"
    )

    st.caption(
        f"Allowed code range: 0 to {(1 << dac_bits) - 1}."
    )

    if st.button("Run DAC", type="primary"):
        try:
            tokens = [
                token.strip().replace("_", "")
                for token in re.split(r"[,;\s]+", code_text.strip())
                if token.strip()
            ]

            if not tokens:
                raise ValueError("Enter at least one digital code.")

            codes = []

            for token in tokens:
                if input_format == "Binary":
                    if not re.fullmatch(r"[01]+", token):
                        raise ValueError(
                            f"{token} is not a valid binary code."
                        )

                    if len(token) > dac_bits:
                        raise ValueError(
                            f"{token} exceeds the selected bit width."
                        )

                    code = int(token, 2)

                else:
                    if not re.fullmatch(r"\d+", token):
                        raise ValueError(
                            f"{token} is not a valid decimal code."
                        )

                    code = int(token)

                if not 0 <= code < (1 << dac_bits):
                    raise ValueError(
                        f"Code must be between 0 and "
                        f"{(1 << dac_bits) - 1}."
                    )

                codes.append(code)

            vref_mv = round(dac_vref * 1000)

            result, raw_output = simulate_verilog(
                "DAC", codes, dac_bits, vref_mv
            )

            output_mv = [voltage for _, voltage in result]

            rows = [{
                "Sample": i,
                "Digital_decimal": code,
                "Digital_binary": format(code, f"0{dac_bits}b"),
                "Output_voltage_V": round(mv / 1000, 6),
            } for i, (code, mv) in enumerate(zip(codes, output_mv))]

            if len(codes) == 1:
                st.success(
                    f"{format(codes[0], f'0{dac_bits}b')} "
                    f"({codes[0]}) → {output_mv[0] / 1000:.6f} V"
                )

            st.subheader("DAC analog output")

            fig, ax = plt.subplots(figsize=(10, 4))
            ax.step(
                range(len(codes)),
                [mv / 1000 for mv in output_mv],
                where="post",
                marker="o"
            )
            ax.set_xlabel("Sample index")
            ax.set_ylabel("Output voltage (V)")
            ax.set_title("Digital code converted to voltage")
            ax.grid(True, alpha=0.3)
            st.pyplot(fig)
            plt.close(fig)

            st.subheader("DAC results")
            st.dataframe(
                pd.DataFrame(rows),
                use_container_width=True,
                hide_index=True
            )

            save_csv(rows, "dac_results.csv")

            with st.expander("Raw Verilog simulation output"):
                st.code(raw_output)

        except Exception as error:
            st.error(str(error))


# --------------------------------------------------
# AI TUTOR
# --------------------------------------------------

with tutor_tab:
    st.header("AI Tutor: Electronics, Verilog and 8086 ALP")

    st.write(
        "Ask about electronic circuits, analog and digital electronics, "
        "ADC/DAC, signals, communication systems, Verilog HDL, testbenches, "
        "program debugging, or 8086 assembly language programs."
    )

    question = st.text_area(
        "Enter your question",
        placeholder=(
            "Explain SAR ADC step by step.\n"
            "Write Verilog code for a 4:1 multiplexer with testbench.\n"
            "Write an 8086 ALP to add two 8-bit numbers."
        ),
        height=140
    )

    def local_fallback(question_text):
        """Provide a non-empty basic response if the AI service fails."""
        q = question_text.lower()

        if "8086" in q or "assembly" in q or " alp" in q:
            return (
                "### 8086 Assembly Language\n"
                "8086 ALP uses instructions such as MOV, ADD, SUB, "
                "INC, DEC, CMP and JMP. A program usually initializes "
                "data, performs the operation, stores the result and "
                "ends according to the assembler or simulator being used.\n\n"
                "Your AI API request failed, so this is only a general "
                "introduction, not a solution to your specific program."
            )

        if "verilog" in q or "testbench" in q or "hdl" in q:
            return (
                "### Verilog HDL\n"
                "A Verilog design declares inputs and outputs, then "
                "describes hardware using continuous assignments or "
                "procedural blocks. A testbench supplies inputs and "
                "checks outputs. Icarus Verilog compiles the design, "
                "and `vvp` runs the compiled simulation.\n\n"
                "Your AI API request failed, so this is only a general "
                "introduction, not the requested complete code."
            )

        if "adc" in q or "dac" in q or "electronics" in q or "circuit" in q:
            return (
                "### Electronics help\n"
                "An ADC converts an analog signal into a digital code. "
                "A DAC converts a digital code into an analog voltage "
                "or current. Other electronics questions may require "
                "circuit assumptions, formulas, diagrams, or step-by-step "
                "calculations.\n\n"
                "Your AI API request failed, so this is only a general "
                "introduction, not a complete answer to your question."
            )

        return (
            "I received your question, but the AI service is currently "
            "unavailable. Please check the API key, model access, network "
            "connection and quota, then try again. The basic fallback "
            "cannot reliably answer every subject-specific question."
        )

    if st.button("Ask AI Tutor", type="primary"):
        if not question.strip():
            st.warning("Enter a question first.")

        else:
            api_key = os.getenv("GEMINI_API_KEY", "").strip()

            if not api_key:
                st.warning(
                    "GEMINI_API_KEY is not configured. Add it in Render's "
                    "Environment settings to enable custom AI answers."
                )
                st.markdown(local_fallback(question))

            else:
                try:
                    from google import genai

                    client = genai.Client(api_key=api_key)

                    prompt = f"""
You are a knowledgeable Electronics and Communication Engineering tutor.

Answer the student's question directly in clear, student-friendly language.
Topics include analog electronics, digital electronics, circuits, signals,
communication systems, measurements, ADC/DAC, microprocessors, 8086 ALP,
8051, Verilog HDL, testbenches, simulation and code debugging.

For code requests:
- Provide complete, syntactically correct code.
- Include required modules and testbenches when requested.
- Explain how to compile or run the code.
- Do not claim to have tested code unless you actually did.

For numerical questions, show formulas, substitutions, units and steps.
For theory, explain the working principle, advantages, disadvantages and
applications when relevant. If assumptions are needed, state them.
Do not leave the answer blank.

Student's question:
{question}
"""

                    with st.spinner("AI Tutor is preparing your answer..."):
                        response = client.models.generate_content(
                            model="gemini-3.8-flash",
                            contents=prompt
                        )

                    answer = (getattr(response, "text", None) or "").strip()

                    if answer:
                        st.markdown(answer)
                    else:
                        st.warning(
                            "The AI returned an empty response. "
                            "Showing the fallback explanation instead."
                        )
                        st.markdown(local_fallback(question))

                except Exception as error:
                    st.error(
                        "The AI service request failed. "
                        "Showing a basic fallback response."
                    )
                    st.markdown(local_fallback(question))
                    st.caption(
                        "Technical details: "
                        + str(error)[:500]
                    )

st.caption(
    "Ideal behavioral simulation. Actual ADC/DAC circuits can have "
    "noise, offset, settling time and nonlinearity."
)



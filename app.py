
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
from openai import OpenAI


# ==================================================
# APPLICATION SETTINGS
# ==================================================

ROOT = Path(__file__).resolve().parent
BITS_OPTIONS = [4, 8, 10, 12, 16]
MAX_SAMPLES = 1000

st.set_page_config(
    page_title="ADC DAC Simulator with AI Tutor",
    page_icon="🔌",
    layout="wide"
)

st.title("ADC & DAC Visual Simulator")
st.caption(
    "Verilog simulation | Adjustable inputs | Graphs | OpenAI AI Tutor"
)


# ==================================================
# VERILOG SIMULATION
# ==================================================

def simulate_verilog(mode, values, bits, vref_mv):
    """Compile and run the selected Verilog testbench."""

    filenames_by_mode = {
        "ADC": ["adc.v", "tb_adc.v"],
        "DAC": ["dac.v", "tb_dac.v"],
    }

    if mode not in filenames_by_mode:
        raise ValueError("Invalid simulation mode.")

    filenames = filenames_by_mode[mode]
    top = "tb_adc" if mode == "ADC" else "tb_dac"
    input_filename = (
        "adc_inputs.txt" if mode == "ADC"
        else "dac_inputs.txt"
    )

    pattern = (
        r"ADC_RESULT\s+(\d+)\s+(\d+)"
        if mode == "ADC"
        else r"DAC_RESULT\s+(\d+)\s+(\d+)"
    )

    for filename in filenames:
        if not (ROOT / filename).is_file():
            raise FileNotFoundError(
                f"Required file is missing: {filename}"
            )

    compiler = shutil.which("iverilog")
    runner = shutil.which("vvp")

    if not compiler or not runner:
        raise RuntimeError(
            "Icarus Verilog was not found. "
            "Check your Dockerfile and Render deployment."
        )

    with tempfile.TemporaryDirectory(
        prefix="adc_dac_sim_"
    ) as temporary_directory:

        work = Path(temporary_directory)

        for filename in filenames:
            shutil.copy2(ROOT / filename, work / filename)

        (work / input_filename).write_text(
            "".join(f"{int(value)}\n" for value in values),
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

        compilation = subprocess.run(
            compile_command,
            cwd=work,
            capture_output=True,
            text=True,
            timeout=30,
        )

        if compilation.returncode != 0:
            raise RuntimeError(
                "Verilog compilation failed:\n"
                + compilation.stdout
                + compilation.stderr
            )

        execution = subprocess.run(
            [runner, "simulation.out"],
            cwd=work,
            capture_output=True,
            text=True,
            timeout=30,
        )

        if execution.returncode != 0:
            raise RuntimeError(
                "Verilog simulation failed:\n"
                + execution.stdout
                + execution.stderr
            )

        matches = re.findall(pattern, execution.stdout)

        if len(matches) != len(values):
            raise RuntimeError(
                "The simulation did not return all expected results.\n"
                + execution.stdout
            )

        results = [
            (int(first), int(second))
            for first, second in matches
        ]

        return results, execution.stdout


# ==================================================
# WAVEFORM GENERATION
# ==================================================

def waveform_value(kind, time, frequency, minimum, maximum):
    phase = (frequency * time) % 1.0

    if kind == "Sine":
        unit_value = math.sin(2 * math.pi * phase)

    elif kind == "Square":
        unit_value = 1.0 if phase < 0.5 else -1.0

    elif kind == "Triangle":
        unit_value = 1.0 - 4.0 * abs(phase - 0.5)

    else:  # Sawtooth
        unit_value = 2.0 * phase - 1.0

    midpoint = (minimum + maximum) / 2.0
    amplitude = (maximum - minimum) / 2.0

    return midpoint + amplitude * unit_value


def generate_waveform(
    kind, minimum, maximum, frequency, sampling_rate, cycles
):
    duration = cycles / frequency

    requested_samples = math.floor(
        duration * sampling_rate
    ) + 1

    sample_count = min(
        MAX_SAMPLES,
        max(2, requested_samples)
    )

    times = [
        index / sampling_rate
        for index in range(sample_count)
    ]

    voltages = [
        waveform_value(
            kind, time, frequency, minimum, maximum
        )
        for time in times
    ]

    # A separate dense curve makes the waveform easier to view.
    curve_count = 500

    curve_times = [
        duration * index / (curve_count - 1)
        for index in range(curve_count)
    ]

    curve_voltages = [
        waveform_value(
            kind, time, frequency, minimum, maximum
        )
        for time in curve_times
    ]

    return (
        times,
        voltages,
        curve_times,
        curve_voltages,
        requested_samples > MAX_SAMPLES,
    )


def map_voltage_to_adc(voltage, minimum, maximum, vref_mv):
    """Map the selected waveform range into 0 through Vref."""

    fraction = (voltage - minimum) / (maximum - minimum)
    fraction = max(0.0, min(1.0, fraction))

    return round(fraction * vref_mv)


def download_csv(rows, filename):
    csv_data = pd.DataFrame(rows).to_csv(
        index=False
    ).encode("utf-8")

    st.download_button(
        label="Download CSV results",
        data=csv_data,
        file_name=filename,
        mime="text/csv",
        key=f"download_{filename}",
    )


# ==================================================
# ADC TAB
# ==================================================

adc_tab, dac_tab, tutor_tab = st.tabs(
    ["ADC Simulator", "DAC Simulator", "AI Tutor"]
)

with adc_tab:
    st.header("Analog-to-Digital Converter")

    left, right = st.columns(2)

    with left:
        waveform = st.selectbox(
            "Select waveform",
            ["Sine", "Square", "Triangle", "Sawtooth"],
        )

        minimum = st.number_input(
            "Minimum input voltage (V)",
            min_value=-100.0,
            max_value=100.0,
            value=0.0,
            step=0.5,
        )

        maximum = st.number_input(
            "Maximum input voltage (V)",
            min_value=-100.0,
            max_value=100.0,
            value=5.0,
            step=0.5,
        )

        frequency = st.number_input(
            "Signal frequency (Hz)",
            min_value=0.1,
            max_value=100000.0,
            value=100.0,
            step=10.0,
        )

    with right:
        sampling_rate = st.number_input(
            "Sampling frequency (samples/second)",
            min_value=1.0,
            max_value=1000000.0,
            value=1000.0,
            step=100.0,
        )

        cycles = st.number_input(
            "Number of cycles",
            min_value=1,
            max_value=10,
            value=2,
        )

        adc_bits = st.selectbox(
            "ADC resolution",
            BITS_OPTIONS,
            index=1,
            format_func=lambda value:
                f"{value} bits ({2**value} levels)",
        )

        adc_vref = st.number_input(
            "ADC reference voltage (V)",
            min_value=0.1,
            max_value=10.0,
            value=5.0,
            step=0.1,
        )

    st.info(
        "This educational model maps the selected waveform's "
        "minimum and maximum to 0 V and the ADC reference voltage. "
        "It can therefore demonstrate negative input ranges, but "
        "it does not model a physical bipolar ADC."
    )

    if sampling_rate < 2 * frequency:
        st.warning(
            "The sampling frequency is below twice the signal "
            "frequency. Aliasing may occur."
        )

    if st.button("Run ADC Simulation", type="primary"):
        if maximum <= minimum:
            st.error(
                "Maximum input voltage must be greater than minimum."
            )

        else:
            try:
                (
                    times,
                    analog_voltages,
                    curve_times,
                    curve_voltages,
                    sample_limit_reached,
                ) = generate_waveform(
                    waveform,
                    minimum,
                    maximum,
                    frequency,
                    sampling_rate,
                    cycles,
                )

                if sample_limit_reached:
                    st.warning(
                        f"The requested waveform needs more than "
                        f"{MAX_SAMPLES} samples. The display is capped "
                        f"at {MAX_SAMPLES} samples, so it covers only "
                        f"the beginning of the requested time window."
                    )

                vref_mv = round(adc_vref * 1000)

                adc_inputs = [
                    map_voltage_to_adc(
                        voltage,
                        minimum,
                        maximum,
                        vref_mv,
                    )
                    for voltage in analog_voltages
                ]

                simulation_results, raw_output = simulate_verilog(
                    "ADC",
                    adc_inputs,
                    adc_bits,
                    vref_mv,
                )

                codes = [
                    code for _, code in simulation_results
                ]

                max_code = (1 << adc_bits) - 1

                represented_voltages = [
                    minimum
                    + (code / max_code) * (maximum - minimum)
                    for code in codes
                ]

                st.subheader("Input waveform")

                fig, ax = plt.subplots(figsize=(10, 4))

                ax.plot(
                    curve_times,
                    curve_voltages,
                    label="Analog waveform",
                )

                ax.scatter(
                    times,
                    analog_voltages,
                    s=18,
                    label="Sampling points",
                )

                ax.set_xlabel("Time (seconds)")
                ax.set_ylabel("Input voltage (V)")
                ax.set_title(f"{waveform} waveform")
                ax.grid(True, alpha=0.3)
                ax.legend()

                st.pyplot(fig)
                plt.close(fig)

                st.subheader("Digital output codes")

                fig, ax = plt.subplots(figsize=(10, 4))

                ax.step(
                    times,
                    codes,
                    where="post",
                )

                ax.set_xlabel("Time (seconds)")
                ax.set_ylabel(f"Digital code (0–{max_code})")
                ax.set_title(f"{adc_bits}-bit ADC output")
                ax.grid(True, alpha=0.3)

                st.pyplot(fig)
                plt.close(fig)

                rows = []

                for index, (
                    time,
                    voltage,
                    code,
                    represented_voltage,
                ) in enumerate(
                    zip(
                        times,
                        analog_voltages,
                        codes,
                        represented_voltages,
                    )
                ):
                    rows.append({
                        "Sample": index,
                        "Time_s": round(time, 8),
                        "Input_voltage_V": round(voltage, 6),
                        "ADC_input_mV": adc_inputs[index],
                        "Digital_decimal": code,
                        "Digital_binary": format(
                            code, f"0{adc_bits}b"
                        ),
                        "Represented_voltage_V": round(
                            represented_voltage, 6
                        ),
                    })

                st.subheader("Sample-by-sample results")

                st.dataframe(
                    pd.DataFrame(rows),
                    use_container_width=True,
                    hide_index=True,
                )

                col1, col2, col3 = st.columns(3)

                col1.metric(
                    "Number of samples",
                    len(codes),
                )

                col2.metric(
                    "Digital levels",
                    1 << adc_bits,
                )

                col3.metric(
                    "Ideal step across selected range",
                    f"{(maximum - minimum) / max_code:.6f} V",
                )

                download_csv(rows, "adc_results.csv")

                with st.expander("Verilog simulation output"):
                    st.code(raw_output)

            except Exception as error:
                st.error("ADC simulation failed.")
                st.code(str(error)[:2000])


# ==================================================
# DAC TAB
# ==================================================

with dac_tab:
    st.header("Digital-to-Analog Converter")

    dac_bits = st.selectbox(
        "DAC resolution",
        BITS_OPTIONS,
        index=1,
        format_func=lambda value:
            f"{value} bits ({2**value} levels)",
    )

    dac_vref = st.number_input(
        "DAC reference voltage (V)",
        min_value=0.1,
        max_value=10.0,
        value=5.0,
        step=0.1,
    )

    input_format = st.radio(
        "Digital input format",
        ["Decimal", "Binary"],
        horizontal=True,
    )

    default_codes = (
        "0, 64, 128, 192, 255"
        if dac_bits == 8
        else "0, 1, 2, 3"
    )

    code_text = st.text_area(
        "Enter digital codes separated by commas",
        value=default_codes,
        help=(
            "Example: decimal 0, 64, 128, 255 "
            "or binary 00000000, 01000000, 11111111."
        ),
    )

    max_dac_code = (1 << dac_bits) - 1

    st.caption(
        f"Valid digital code range: 0 to {max_dac_code}."
    )

    if st.button("Run DAC Simulation", type="primary"):
        try:
            tokens = [
                token.strip().replace("_", "")
                for token in re.split(
                    r"[,;\s]+", code_text.strip()
                )
                if token.strip()
            ]

            if not tokens:
                raise ValueError(
                    "Enter at least one digital code."
                )

            codes = []

            for token in tokens:
                if input_format == "Binary":
                    if not re.fullmatch(r"[01]+", token):
                        raise ValueError(
                            f"'{token}' is not a valid binary code."
                        )

                    if len(token) > dac_bits:
                        raise ValueError(
                            f"'{token}' exceeds the selected "
                            f"{dac_bits}-bit resolution."
                        )

                    code = int(token, 2)

                else:
                    if not re.fullmatch(r"\d+", token):
                        raise ValueError(
                            f"'{token}' is not a valid decimal code."
                        )

                    code = int(token)

                if not 0 <= code <= max_dac_code:
                    raise ValueError(
                        f"Code {code} is outside the range "
                        f"0 to {max_dac_code}."
                    )

                codes.append(code)

            vref_mv = round(dac_vref * 1000)

            simulation_results, raw_output = simulate_verilog(
                "DAC",
                codes,
                dac_bits,
                vref_mv,
            )

            output_mv = [
                voltage for _, voltage in simulation_results
            ]

            rows = []

            for index, (code, voltage_mv) in enumerate(
                zip(codes, output_mv)
            ):
                rows.append({
                    "Sample": index,
                    "Digital_decimal": code,
                    "Digital_binary": format(
                        code, f"0{dac_bits}b"
                    ),
                    "Output_voltage_V": round(
                        voltage_mv / 1000, 6
                    ),
                })

            if len(codes) == 1:
                st.success(
                    f"Digital code {format(codes[0], f'0{dac_bits}b')} "
                    f"produces approximately "
                    f"{output_mv[0] / 1000:.6f} V."
                )

            st.subheader("Analog output voltage")

            fig, ax = plt.subplots(figsize=(10, 4))

            ax.step(
                range(len(codes)),
                [voltage / 1000 for voltage in output_mv],
                where="post",
                marker="o",
            )

            ax.set_xlabel("Sample index")
            ax.set_ylabel("Output voltage (V)")
            ax.set_title("DAC output")
            ax.grid(True, alpha=0.3)

            st.pyplot(fig)
            plt.close(fig)

            st.subheader("DAC conversion results")

            st.dataframe(
                pd.DataFrame(rows),
                use_container_width=True,
                hide_index=True,
            )

            download_csv(rows, "dac_results.csv")

            with st.expander("Verilog simulation output"):
                st.code(raw_output)

        except Exception as error:
            st.error("DAC simulation failed.")
            st.code(str(error)[:2000])


# ==================================================
# AI TUTOR
# ==================================================

def local_fallback(question):
    """Basic response if the online AI service is unavailable."""

    q = question.lower()

    if "8086" in q or "assembly language" in q or " alp" in q:
        return (
            "### 8086 Assembly Language\n\n"
            "8086 programs use instructions such as MOV, ADD, SUB, "
            "INC, DEC, CMP and JMP. A program usually initializes "
            "data, performs an operation, stores its result and "
            "finishes according to the assembler being used.\n\n"
            "The AI service is unavailable, so this is only a "
            "general introduction, not a complete solution."
        )

    if "verilog" in q or "testbench" in q or "hdl" in q:
        return (
            "### Verilog HDL\n\n"
            "Verilog describes digital hardware using modules, "
            "inputs, outputs and logic. A testbench applies input "
            "stimuli and checks the design's output. Icarus Verilog "
            "can compile and simulate supported Verilog designs.\n\n"
            "The AI service is unavailable, so this is only a "
            "general introduction, not complete custom code."
        )

    if "adc" in q or "dac" in q or "electronics" in q:
        return (
            "### Electronics\n\n"
            "An ADC converts an analog signal into a digital code. "
            "A DAC converts a digital code into an analog voltage "
            "or current. More detailed answers depend on the "
            "specific circuit or question.\n\n"
            "The AI service is unavailable, so this is only a "
            "general introduction."
        )

    return (
        "The AI service is currently unavailable. Check your "
        "API key, account access, available API credits, model "
        "access and network connection, then try again."
    )


with tutor_tab:
    st.header("AI Tutor")

    st.write(
        "Ask questions about electronics theory, analog circuits, "
        "digital electronics, ADC/DAC, signal processing, "
        "Verilog HDL, testbenches, debugging, or 8086 ALP."
    )

    question = st.text_area(
        "Enter your question",
        placeholder=(
            "Explain SAR ADC step by step.\n"
            "Write Verilog code for a 4:1 multiplexer "
            "with a testbench.\n"
            "Write an 8086 ALP to add two 8-bit numbers."
        ),
        height=150,
        key="tutor_question",
    )

    if st.button("Ask AI Tutor", type="primary"):
        if not question.strip():
            st.warning("Please enter a question first.")

        else:
            api_key = os.getenv("OPENAI_API_KEY", "").strip()

            if not api_key:
                st.error(
                    "OPENAI_API_KEY is missing. Add it in your "
                    "Render Environment settings."
                )
                st.markdown(local_fallback(question))

            else:
                try:
                    client = OpenAI(
                        api_key=api_key,
                        timeout=30.0,
                        max_retries=1,
                    )

                    instructions = """
You are an Electronics and Communication Engineering tutor.

Answer the student's actual question clearly and completely
using student-friendly language.

You can help with:
- Analog and digital electronics
- Electronic circuits and circuit analysis
- ADC, DAC, filters, oscillators and amplifiers
- Signals, systems and communication systems
- Measurements and instrumentation
- 8086 assembly language programs
- 8051 microcontroller programming
- Verilog HDL and testbenches
- Simulation errors and debugging

For programming questions:
1. Provide complete code when requested.
2. Include a testbench when requested.
3. Explain the important instructions and logic.
4. Show how to compile or simulate the code when useful.
5. Do not claim the code was executed unless it actually was.

For numerical questions, show the formula, substitution,
units and calculation steps. For theory questions, explain
the working principle in clear language and include relevant
applications when appropriate.

If a detail is missing, state a reasonable assumption.
Do not replace the student's specific question with a
generic introduction.
"""

                    with st.spinner(
                        "AI Tutor is generating your answer..."
                    ):
                        response = client.responses.create(
                            model="gpt-5.5",
                            instructions=instructions,
                            input=question.strip(),
                        )

                    answer = (
                        getattr(response, "output_text", "") or ""
                    ).strip()

                    if answer:
                        st.subheader("AI Tutor Answer")
                        st.markdown(answer)
                    else:
                        st.warning(
                            "The API returned an empty answer. "
                            "Please try again."
                        )
                        st.markdown(local_fallback(question))

                except Exception as error:
                    st.error(
                        "The OpenAI request failed. "
                        "Check the technical details below."
                    )

                    st.markdown(local_fallback(question))

                    with st.expander("Technical details"):
                        st.code(str(error)[:2000])


# ==================================================
# FOOTER
# ==================================================

st.divider()

st.caption(
    "Educational ideal-converter simulation. Physical ADCs and "
    "DACs may have noise, offset, settling time and nonlinearity. "
    "AI responses require a working OpenAI API connection."
)



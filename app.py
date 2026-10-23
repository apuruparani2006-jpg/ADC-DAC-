
import os
import math
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st
from groq import Groq


# =========================================================
# PAGE CONFIGURATION
# =========================================================

st.set_page_config(
    page_title="ADC & DAC AI Tutor",
    page_icon="⚡",
    layout="wide"
)

BASE_DIR = Path(__file__).resolve().parent

st.title("⚡ ADC & DAC Visual Simulator")
st.write(
    "Simulate Analog-to-Digital and Digital-to-Analog "
    "conversion using Verilog, with an AI Tutor for ECE."
)


# =========================================================
# SIDEBAR SETTINGS
# =========================================================

st.sidebar.title("⚙️ Settings")

api_key = st.sidebar.text_input(
    "Groq API Key",
    value=os.getenv("GROQ_API_KEY", ""),
    type="password",
    help="Get your key from https://console.groq.com/"
)

model_name = st.sidebar.text_input(
    "Groq model",
    value="llama-3.3-70b-versatile"
)

st.sidebar.caption(
    "Your API key is used by this app to contact Groq. "
    "Avoid sharing it or committing it to GitHub."
)


# =========================================================
# VERILOG SIMULATION FUNCTION
# =========================================================

def simulate_verilog(mode, values, bits, vref_mv):
    """
    Run the ADC or DAC Verilog module using Icarus Verilog.

    mode: 'adc' or 'dac'
    values: list of input voltages (mV) or digital codes
    bits: resolution
    vref_mv: reference voltage in millivolts
    """

    if not shutil.which("iverilog"):
        raise RuntimeError(
            "Icarus Verilog (iverilog) was not found. "
            "Install it or run this project using the supplied Dockerfile."
        )

    if not shutil.which("vvp"):
        raise RuntimeError(
            "The vvp simulator was not found. "
            "Check your Icarus Verilog installation."
        )

    if mode not in ("adc", "dac"):
        raise ValueError("Simulation mode must be adc or dac.")

    module_file = BASE_DIR / f"{mode}.v"
    testbench_file = BASE_DIR / f"tb_{mode}.v"

    if not module_file.exists():
        raise FileNotFoundError(f"Missing file: {module_file.name}")

    if not testbench_file.exists():
        raise FileNotFoundError(f"Missing file: {testbench_file.name}")

    max_code = (1 << bits) - 1

    with tempfile.TemporaryDirectory() as temp_dir:
        work_dir = Path(temp_dir)

        shutil.copy2(module_file, work_dir / module_file.name)
        shutil.copy2(testbench_file, work_dir / testbench_file.name)

        input_filename = f"{mode}_inputs.txt"
        input_path = work_dir / input_filename

        with open(input_path, "w", encoding="utf-8") as file:
            for value in values:
                file.write(f"{int(value)}\n")

        testbench_name = f"tb_{mode}"

        compile_command = [
            "iverilog",
            "-g2012",
            "-s", testbench_name,
            f"-P{testbench_name}.BITS={bits}",
            f"-P{testbench_name}.VREF_MV={vref_mv}",
            "-o", "simulation.out",
            module_file.name,
            testbench_file.name
        ]

        compilation = subprocess.run(
            compile_command,
            cwd=work_dir,
            capture_output=True,
            text=True,
            timeout=30
        )

        if compilation.returncode != 0:
            raise RuntimeError(
                "Verilog compilation failed:\n"
                + compilation.stderr
                + compilation.stdout
            )

        execution = subprocess.run(
            ["vvp", "simulation.out"],
            cwd=work_dir,
            capture_output=True,
            text=True,
            timeout=30
        )

        if execution.returncode != 0:
            raise RuntimeError(
                "Verilog simulation failed:\n"
                + execution.stderr
                + execution.stdout
            )

        output_text = execution.stdout
        pattern = r"(ADC_RESULT|DAC_RESULT)\s+(\d+)\s+(\d+)"

        matches = re.findall(pattern, output_text)

        results = []

        for result_type, first, second in matches:
            if result_type == "ADC_RESULT" and mode == "adc":
                results.append({
                    "Input (mV)": int(first),
                    "Digital Code": int(second)
                })

            elif result_type == "DAC_RESULT" and mode == "dac":
                results.append({
                    "Digital Code": int(first),
                    "Output (mV)": int(second)
                })

        if len(results) != len(values):
            raise RuntimeError(
                "The simulator did not return all expected results. "
                "Check the Verilog testbench output."
            )

        return results


# =========================================================
# WAVEFORM GENERATION
# =========================================================

def waveform_value(waveform, phase):
    """Return a normalized waveform value between 0 and 1."""

    phase = phase % 1.0

    if waveform == "Sine":
        return 0.5 + 0.5 * math.sin(2 * math.pi * phase)

    if waveform == "Square":
        return 1.0 if phase < 0.5 else 0.0

    if waveform == "Triangle":
        return 1.0 - abs(2.0 * phase - 1.0)

    if waveform == "Sawtooth":
        return phase

    return 0.5


def generate_waveform(
    waveform,
    min_voltage,
    max_voltage,
    frequency,
    sampling_frequency,
    cycles
):
    """
    Generate sample points and a dense curve for plotting.

    Returns:
        sample_times
        sample_voltages
        curve_times
        curve_voltages
    """

    duration = cycles / frequency

    # Limit the sample count so large settings do not
    # overload the web application.
    number_of_samples = int(
        math.floor(duration * sampling_frequency)
    ) + 1

    if number_of_samples > 1000:
        raise ValueError(
            "This setting creates more than 1000 samples. "
            "Reduce the sampling frequency or number of cycles."
        )

    sample_times = [
        i / sampling_frequency
        for i in range(number_of_samples)
    ]

    sample_voltages = [
        min_voltage
        + (
            max_voltage - min_voltage
        ) * waveform_value(
            waveform, time_value * frequency
        )
        for time_value in sample_times
    ]

    curve_count = max(
        400,
        min(3000, number_of_samples * 20)
    )

    curve_times = [
        duration * i / (curve_count - 1)
        for i in range(curve_count)
    ]

    curve_voltages = [
        min_voltage
        + (
            max_voltage - min_voltage
        ) * waveform_value(
            waveform, time_value * frequency
        )
        for time_value in curve_times
    ]

    return (
        sample_times,
        sample_voltages,
        curve_times,
        curve_voltages
    )


# =========================================================
# HELPER FUNCTIONS
# =========================================================

def code_to_binary(code, bits):
    return format(int(code), f"0{bits}b")


def csv_download_button(dataframe, filename, label):
    csv_data = dataframe.to_csv(index=False).encode("utf-8")

    st.download_button(
        label=label,
        data=csv_data,
        file_name=filename,
        mime="text/csv"
    )


def parse_dac_codes(text, input_format, bits):
    """Parse decimal or binary codes entered by the user."""

    tokens = [
        token
        for token in re.split(r"[\s,;]+", text.strip())
        if token
    ]

    if not tokens:
        raise ValueError("Enter at least one digital code.")

    max_code = (1 << bits) - 1
    codes = []

    for token in tokens:
        if input_format == "Binary":
            if not re.fullmatch(r"[01]+", token):
                raise ValueError(
                    f"'{token}' is not a valid binary number."
                )

            value = int(token, 2)

        else:
            if not re.fullmatch(r"\d+", token):
                raise ValueError(
                    f"'{token}' is not a valid decimal number."
                )

            value = int(token, 10)

        if value < 0 or value > max_code:
            raise ValueError(
                f"Code {token} is outside the permitted range "
                f"0 to {max_code} for {bits}-bit resolution."
            )

        codes.append(value)

    if len(codes) > 1000:
        raise ValueError("Enter no more than 1000 digital codes.")

    return codes


# =========================================================
# AI TUTOR FUNCTIONS
# =========================================================

def local_fallback(question):
    """
    Basic explanations for common topics when no API key
    is available or the AI service cannot be reached.
    """

    q = question.lower()

    if "adc" in q or "analog to digital" in q:
        return """
### Analog-to-Digital Converter (ADC)

An ADC converts an analog input voltage into a digital number.

**Working:**
1. The analog signal is sampled at particular time intervals.
2. Each sample is converted into a digital code.
3. The bit resolution determines how many codes are available.
4. The reference voltage determines the conversion range.

For an N-bit converter, the maximum code is:

Maximum code = 2^N - 1

For example, an 8-bit ADC produces codes from 0 to 255.
"""

    if "dac" in q or "digital to analog" in q:
        return """
### Digital-to-Analog Converter (DAC)

A DAC converts a digital code into an approximate analog voltage.

**Working:**
1. A digital code is applied at the input.
2. The converter uses its bit resolution and reference voltage.
3. It produces the corresponding output voltage.

For the endpoint mapping used in this project:

Output voltage ≈ Digital code × Vref / (2^N - 1)

The output is an approximation of the desired analog signal.
"""

    if "resolution" in q or "number of bits" in q:
        return """
### Converter Resolution

An N-bit ADC or DAC represents 2^N different digital codes.

Examples:

- 4-bit: 16 codes, from 0 to 15
- 8-bit: 256 codes, from 0 to 255
- 10-bit: 1024 codes, from 0 to 1023
- 12-bit: 4096 codes, from 0 to 4095
- 16-bit: 65536 codes, from 0 to 65535

Increasing resolution provides more possible output levels.
"""

    if "sampling" in q or "nyquist" in q:
        return """
### Sampling Frequency

Sampling frequency is the number of samples taken per second.

It is measured in hertz (Hz).

For a periodic signal with frequency f, the Nyquist criterion
states that the sampling frequency should be greater than
twice the highest signal frequency to avoid aliasing under
ideal band-limited sampling conditions.

In practice, additional sampling margin and an appropriate
anti-aliasing filter are often required.
"""

    if "verilog" in q or "testbench" in q:
        return """
### Verilog and Testbenches

Verilog is a hardware description language used to describe
and simulate digital circuits.

- A module defines the circuit.
- Inputs and outputs describe its connections.
- An always block describes logic that responds to changes.
- A testbench supplies input values and checks or displays results.

Icarus Verilog compiles the modules, and vvp runs the simulation.
"""

    if "8086" in q or "assembly" in q or "alp" in q:
        return """
### 8086 Assembly Language Programming

8086 ALP uses instructions to perform operations in the
8086 microprocessor.

Common instructions:

- MOV: transfers data
- ADD: adds values
- SUB: subtracts values
- INC: increments a value
- DEC: decrements a value
- CMP: compares values
- JMP: changes program flow

A complete program depends on the operation being performed.
"""

    if "op amp" in q or "operational amplifier" in q:
        return """
### Operational Amplifier

An operational amplifier (op-amp) is a high-gain electronic
amplifier with two inputs: inverting and non-inverting.

Op-amps are used in amplifiers, filters, comparators,
integrators, differentiators, and signal-conditioning circuits.

Negative feedback can help set a predictable closed-loop gain.
"""

    return (
        "I could not generate a customized answer because "
        "the Groq AI service is unavailable or no API key was "
        "provided. Add a valid Groq API key to ask broader "
        "questions about electronics, Verilog, or 8086 ALP."
    )


def ask_ai(question, key, model):
    """Send the question to Groq and return its answer."""

    if not key.strip():
        return local_fallback(question), (
            "No Groq API key was entered. "
            "A local explanation was shown where available."
        )

    try:
        client = Groq(
            api_key=key.strip(),
            timeout=30.0,
            max_retries=1
        )

        response = client.chat.completions.create(
            model=model.strip(),
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an educational AI Tutor for "
                        "Electronics and Communication Engineering. "
                        "Explain concepts in clear, student-friendly "
                        "language. Help with ADC, DAC, analog "
                        "electronics, digital electronics, signal "
                        "processing, Verilog HDL, Verilog testbenches, "
                        "and 8086 Assembly Language Programming. "
                        "For numerical problems, show the formula, "
                        "substitution, calculation, and final answer. "
                        "For code requests, provide complete, "
                        "readable code and explain how it works. "
                        "Do not invent simulation results."
                    )
                },
                {
                    "role": "user",
                    "content": question.strip()
                }
            ],
            temperature=0.3,
            max_completion_tokens=2500
        )

        answer = response.choices[0].message.content

        if not answer:
            return (
                "The AI service returned an empty answer.",
                "Please try asking the question again."
            )

        return answer, None

    except Exception as error:
        # Avoid displaying API keys or sensitive configuration.
        st.error(
            "The Groq request failed. Check the API key, "
            "model name, network connection, and API limits."
        )

        st.caption(f"Technical detail: {type(error).__name__}")

        return local_fallback(question), (
            "The local fallback explanation is shown below."
        )


# =========================================================
# APPLICATION TABS
# =========================================================

adc_tab, dac_tab, tutor_tab, about_tab = st.tabs(
    [
        "📈 ADC Simulator",
        "📉 DAC Simulator",
        "🤖 AI Tutor",
        "ℹ️ About"
    ]
)


# =========================================================
# ADC SIMULATOR
# =========================================================

with adc_tab:

    st.header("Analog-to-Digital Converter")

    st.write(
        "Select an analog waveform, configure its frequency "
        "and sampling rate, and observe the digital output "
        "generated by the Verilog ADC module."
    )

    left, right = st.columns(2)

    with left:
        waveform = st.selectbox(
            "Input waveform",
            ["Sine", "Square", "Triangle", "Sawtooth"]
        )

        min_voltage = st.number_input(
            "Minimum voltage (V)",
            min_value=0.0,
            max_value=10.0,
            value=0.0,
            step=0.1
        )

        max_voltage = st.number_input(
            "Maximum voltage (V)",
            min_value=0.0,
            max_value=10.0,
            value=5.0,
            step=0.1
        )

        frequency = st.number_input(
            "Signal frequency (Hz)",
            min_value=1.0,
            max_value=10000.0,
            value=10.0,
            step=1.0
        )

    with right:
        sampling_frequency = st.number_input(
            "Sampling frequency (Hz)",
            min_value=1.0,
            max_value=100000.0,
            value=100.0,
            step=10.0
        )

        cycles = st.slider(
            "Number of signal cycles",
            min_value=1,
            max_value=5,
            value=2
        )

        adc_bits = st.selectbox(
            "ADC resolution (bits)",
            [4, 8, 10, 12, 16],
            index=1
        )

        adc_vref = st.number_input(
            "Reference voltage Vref (V)",
            min_value=0.1,
            max_value=10.0,
            value=5.0,
            step=0.1
        )

    adc_run = st.button(
        "▶ Run ADC Simulation",
        type="primary",
        key="run_adc"
    )

    if adc_run:

        if max_voltage <= min_voltage:
            st.error(
                "Maximum voltage must be greater than "
                "minimum voltage."
            )

        else:
            duration = cycles / frequency
            estimated_samples = (
                math.floor(duration * sampling_frequency) + 1
            )

            if estimated_samples > 1000:
                st.error(
                    "The selected settings generate more than "
                    "1000 samples. Reduce the sampling frequency "
                    "or number of cycles."
                )

            else:
                try:
                    (
                        sample_times,
                        sample_voltages,
                        curve_times,
                        curve_voltages
                    ) = generate_waveform(
                        waveform,
                        min_voltage,
                        max_voltage,
                        frequency,
                        sampling_frequency,
                        cycles
                    )

                    vref_mv = round(adc_vref * 1000)

                    # The Verilog ADC input is unsigned.
                    # Convert volts to millivolts and limit
                    # values to the converter's input range.
                    sample_mv = [
                        max(
                            0,
                            min(
                                vref_mv,
                                round(voltage * 1000)
                            )
                        )
                        for voltage in sample_voltages
                    ]

                    with st.spinner(
                        "Compiling and running Verilog ADC..."
                    ):
                        adc_results = simulate_verilog(
                            "adc",
                            sample_mv,
                            adc_bits,
                            vref_mv
                        )

                    digital_codes = [
                        item["Digital Code"]
                        for item in adc_results
                    ]

                    binary_codes = [
                        code_to_binary(code, adc_bits)
                        for code in digital_codes
                    ]

                    # -----------------------------------------
                    # ADC INPUT WAVEFORM
                    # -----------------------------------------

                    st.subheader("1. Analog Input Waveform")

                    fig1, ax1 = plt.subplots(figsize=(10, 4))

                    ax1.plot(
                        curve_times,
                        curve_voltages,
                        label="Analog waveform"
                    )

                    ax1.scatter(
                        sample_times,
                        sample_voltages,
                        label="Sampling points",
                        s=25
                    )

                    ax1.set_xlabel("Time (seconds)")
                    ax1.set_ylabel("Voltage (V)")
                    ax1.set_title(
                        f"{waveform} Waveform and Sampling Points"
                    )
                    ax1.grid(True)
                    ax1.legend()
                    fig1.tight_layout()

                    st.pyplot(fig1)
                    plt.close(fig1)

                    # -----------------------------------------
                    # DIGITAL OUTPUT WAVEFORM
                    # -----------------------------------------

                    st.subheader("2. Digital Output")

                    fig2, ax2 = plt.subplots(figsize=(10, 4))

                    ax2.step(
                        sample_times,
                        digital_codes,
                        where="post",
                        label="ADC digital code"
                    )

                    ax2.scatter(
                        sample_times,
                        digital_codes,
                        s=20
                    )

                    ax2.set_xlabel("Time (seconds)")
                    ax2.set_ylabel("Digital code")
                    ax2.set_title(
                        f"{adc_bits}-bit ADC Digital Output"
                    )
                    ax2.grid(True)
                    ax2.legend()
                    fig2.tight_layout()

                    st.pyplot(fig2)
                    plt.close(fig2)

                    # -----------------------------------------
                    # ADC RESULTS TABLE
                    # -----------------------------------------

                    st.subheader("3. Conversion Results")

                    adc_table = pd.DataFrame({
                        "Time (s)": sample_times,
                        "Analog Voltage (V)": sample_voltages,
                        "Input to ADC (mV)": sample_mv,
                        "Digital Code (Decimal)": digital_codes,
                        "Digital Code (Binary)": binary_codes
                    })

                    st.dataframe(
                        adc_table,
                        use_container_width=True,
                        hide_index=True
                    )

                    csv_download_button(
                        adc_table,
                        "adc_results.csv",
                        "⬇ Download ADC Results (CSV)"
                    )

                    st.success(
                        f"Simulation completed: "
                        f"{len(adc_results)} samples, "
                        f"{adc_bits}-bit resolution."
                    )

                    st.caption(
                        "Note: ADC input voltages above Vref are "
                        "clipped to Vref. The displayed analog "
                        "waveform shows the requested input, while "
                        "the conversion uses the clipped values."
                    )

                except Exception as error:
                    st.error("ADC simulation failed.")
                    st.code(str(error))


# =========================================================
# DAC SIMULATOR
# =========================================================

with dac_tab:

    st.header("Digital-to-Analog Converter")

    st.write(
        "Enter digital codes and observe the corresponding "
        "output voltage produced by the Verilog DAC module."
    )

    dac_bits = st.selectbox(
        "DAC resolution (bits)",
        [4, 8, 10, 12, 16],
        index=1,
        key="dac_bits"
    )

    dac_vref = st.number_input(
        "DAC reference voltage Vref (V)",
        min_value=0.1,
        max_value=10.0,
        value=5.0,
        step=0.1,
        key="dac_vref"
    )

    input_format = st.radio(
        "Digital code format",
        ["Decimal", "Binary"],
        horizontal=True
    )

    if input_format == "Decimal":
        default_codes = "0, 32, 64, 128, 192, 255"
        input_hint = (
            "Enter decimal values separated by commas, "
            "spaces, or new lines."
        )
    else:
        default_codes = "00000000, 00100000, 01000000, 10000000, 11111111"
        input_hint = (
            "Enter binary values separated by commas, "
            "spaces, or new lines."
        )

    digital_input = st.text_area(
        "Digital input codes",
        value=default_codes,
        height=110,
        help=input_hint
    )

    st.caption(
        f"For {dac_bits}-bit resolution, valid decimal codes "
        f"are 0 to {(1 << dac_bits) - 1}. "
        "Binary inputs may use leading zeros."
    )

    dac_run = st.button(
        "▶ Run DAC Simulation",
        type="primary",
        key="run_dac"
    )

    if dac_run:

        try:
            digital_codes = parse_dac_codes(
                digital_input,
                input_format,
                dac_bits
            )

            vref_mv = round(dac_vref * 1000)

            with st.spinner(
                "Compiling and running Verilog DAC..."
            ):
                dac_results = simulate_verilog(
                    "dac",
                    digital_codes,
                    dac_bits,
                    vref_mv
                )

            output_mv = [
                item["Output (mV)"]
                for item in dac_results
            ]

            output_volts = [
                value / 1000.0
                for value in output_mv
            ]

            binary_codes = [
                code_to_binary(code, dac_bits)
                for code in digital_codes
            ]

            # ---------------------------------------------
            # DAC OUTPUT GRAPH
            # ---------------------------------------------

            st.subheader("1. Digital Input and Analog Output")

            fig3, ax3 = plt.subplots(figsize=(10, 4))

            ax3.plot(
                range(len(output_volts)),
                output_volts,
                marker="o",
                label="DAC output voltage"
            )

            ax3.set_xlabel("Input code index")
            ax3.set_ylabel("Output voltage (V)")
            ax3.set_title("DAC Output Voltage")
            ax3.grid(True)
            ax3.legend()
            fig3.tight_layout()

            st.pyplot(fig3)
            plt.close(fig3)

            # ---------------------------------------------
            # DAC RESULTS TABLE
            # ---------------------------------------------

            st.subheader("2. Conversion Results")

            dac_table = pd.DataFrame({
                "Input Code (Decimal)": digital_codes,
                "Input Code (Binary)": binary_codes,
                "Output Voltage (mV)": output_mv,
                "Output Voltage (V)": output_volts
            })

            st.dataframe(
                dac_table,
                use_container_width=True,
                hide_index=True
            )

            csv_download_button(
                dac_table,
                "dac_results.csv",
                "⬇ Download DAC Results (CSV)"
            )

            st.success(
                f"DAC simulation completed for "
                f"{len(digital_codes)} digital codes."
            )

        except Exception as error:
            st.error("DAC simulation failed.")
            st.code(str(error))


# =========================================================
# AI TUTOR
# =========================================================

with tutor_tab:

    st.header("🤖 ECE AI Tutor")

    st.write(
        "Ask questions about electronics, ADC/DAC, Verilog, "
        "testbenches, or 8086 Assembly Language Programming."
    )

    st.caption(
        "A Groq API key is required for customized AI answers. "
        "Without it, the tutor can provide limited built-in explanations."
    )

    if "tutor_history" not in st.session_state:
        st.session_state.tutor_history = []

    # Display previous conversation
    for message in st.session_state.tutor_history:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    question = st.chat_input(
        "Ask your ECE question..."
    )

    if question:
        st.session_state.tutor_history.append({
            "role": "user",
            "content": question
        })

        with st.chat_message("user"):
            st.markdown(question)

        with st.chat_message("assistant"):
            with st.spinner("Preparing your answer..."):
                answer, note = ask_ai(
                    question,
                    api_key,
                    model_name
                )

            st.markdown(answer)

            if note:
                st.caption(note)

        st.session_state.tutor_history.append({
            "role": "assistant",
            "content": answer
        })

    if st.button("Clear Tutor Conversation"):
        st.session_state.tutor_history = []
        st.rerun()


# =========================================================
# ABOUT PAGE
# =========================================================

with about_tab:

    st.header("About This Project")

    st.markdown("""
### Project: ADC & DAC Visual Simulator with AI Tutor

This is a software-only ECE educational project.

**Technologies used**

- **Python:** application logic and calculations
- **Streamlit:** interactive web interface
- **Verilog HDL:** ADC and DAC circuit models
- **Icarus Verilog:** compilation and simulation
- **Matplotlib:** waveform and graph visualization
- **Pandas:** result tables and CSV files
- **Groq API:** AI-powered educational assistance

### ADC operation

The ADC accepts an analog voltage and converts it into
a digital code based on its bit resolution and reference voltage.

### DAC operation

The DAC accepts a digital code and produces a corresponding
output voltage.

### AI Tutor

The tutor can help explain ECE concepts, provide Verilog examples,
discuss testbenches, and assist with 8086 ALP.

### Important limitation

These are educational behavioral models. They demonstrate
conversion and simulation; they do not represent a complete
physical ADC or DAC circuit with all real-world effects.
""")

    st.subheader("Required project files")

    st.code(
        "adc-dac-ai-tutor/\n"
        "├── app.py\n"
        "├── adc.v\n"
        "├── dac.v\n"
        "├── tb_adc.v\n"
        "├── tb_dac.v\n"
        "├── requirements.txt\n"
        "└── Dockerfile",
        language="text"
    )

st.divider()

st.caption(
    "ADC & DAC Visual Simulator | ECE Learning Project"
)




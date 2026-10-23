
import os
import re
import subprocess
from pathlib import Path

import matplotlib.pyplot as plt
import streamlit as st

BASE_DIR = Path(__file__).resolve().parent

st.set_page_config(
    page_title="AI ADC/DAC Lab",
    page_icon="🔬",
    layout="wide"
)

st.title("AI-Powered ADC/DAC Learning Lab")
st.caption("Learn converter theory and run actual Verilog testbenches.")

def run_verilog(output_name, source_files):
    """Compile and run a Verilog testbench using Icarus Verilog."""
    try:
        compile_result = subprocess.run(
            ["iverilog", "-o", output_name] + source_files,
            cwd=BASE_DIR,
            capture_output=True,
            text=True,
            timeout=15
        )

        if compile_result.returncode != 0:
            return None, compile_result.stderr

        run_result = subprocess.run(
            ["vvp", output_name],
            cwd=BASE_DIR,
            capture_output=True,
            text=True,
            timeout=15
        )

        if run_result.returncode != 0:
            return None, run_result.stderr

        return run_result.stdout, None

    except FileNotFoundError:
        return None, (
            "Icarus Verilog was not found. Install it and ensure "
            "both iverilog and vvp are available on PATH."
        )
    except subprocess.TimeoutExpired:
        return None, "Simulation timed out."

def read_rows(output, expected_header):
    """Read comma-separated rows printed by a testbench."""
    rows = []

    for line in output.splitlines():
        line = line.strip()

        if not line or line.startswith("VCD"):
            continue
        if line == expected_header:
            continue
        if "," not in line:
            continue

        match = re.fullmatch(r"(\d+),(\d+)", line)
        if match:
            rows.append((int(match.group(1)), int(match.group(2))))

    return rows

adc_tab, dac_tab, tutor_tab = st.tabs(
    ["ADC Simulation", "DAC Simulation", "AI Tutor"]
)

with adc_tab:
    st.subheader("4-bit ADC")
    st.write(
        "Reference voltage: 3300 mV. "
        "Change the test values in adc_tb.v to explore other inputs."
    )

    if st.button("Run ADC Verilog Simulation"):
        output, error = run_verilog(
            "adc_sim",
            ["adc.v", "adc_tb.v"]
        )

        if error:
            st.error(error)
        else:
            rows = read_rows(output, "Voltage_mV,Digital_Code")

            if not rows:
                st.warning("No data found. Check adc_tb.v output format.")
                st.code(output)
            else:
                st.success("ADC testbench completed.")
                st.dataframe(
                    [
                        {"Input voltage (mV)": v, "Digital code": d,
                         "Binary output": format(d, "04b")}
                        for v, d in rows
                    ],
                    use_container_width=True
                )

                fig, ax = plt.subplots()
                ax.step(
                    [r[0] for r in rows],
                    [r[1] for r in rows],
                    where="post"
                )
                ax.set_xlabel("Input voltage (mV)")
                ax.set_ylabel("4-bit digital code")
                ax.set_title("ADC Transfer Characteristic")
                ax.grid(True)
                st.pyplot(fig)
                plt.close(fig)

                st.caption(
                    "The step-shaped response illustrates quantization: "
                    "a range of input voltages maps to the same code."
                )

with dac_tab:
    st.subheader("4-bit DAC")
    st.write(
        "The DAC maps digital codes 0–15 to nominal output voltages "
        "from 0–3300 mV."
    )

    if st.button("Run DAC Verilog Simulation"):
        output, error = run_verilog(
            "dac_sim",
            ["dac.v", "dac_tb.v"]
        )

        if error:
            st.error(error)
        else:
            rows = read_rows(output, "Digital_Code,Voltage_mV")

            if not rows:
                st.warning("No data found. Check dac_tb.v output format.")
                st.code(output)
            else:
                st.success("DAC testbench completed.")
                st.dataframe(
                    [
                        {"Digital code": d,
                         "Binary input": format(d, "04b"),
                         "Output voltage (mV)": v}
                        for d, v in rows
                    ],
                    use_container_width=True
                )

                fig, ax = plt.subplots()
                ax.plot(
                    [r[0] for r in rows],
                    [r[1] for r in rows],
                    marker="o"
                )
                ax.set_xlabel("4-bit digital input")
                ax.set_ylabel("Output voltage (mV)")
                ax.set_title("DAC Transfer Characteristic")
                ax.grid(True)
                st.pyplot(fig)
                plt.close(fig)

with tutor_tab:
    st.subheader("Ask the AI Electronics Tutor")
    st.write(
        "Ask about Flash ADC, SAR ADC, Dual-Slope ADC, "
        "Binary-Weighted DAC, R–2R Ladder DAC, quantization, "
        "resolution, or the simulation results."
    )

    question = st.text_area(
        "Your question",
        placeholder="Explain how a SAR ADC works with an example."
    )

    if st.button("Ask Tutor"):
        if not question.strip():
            st.warning("Enter a question first.")
        elif not os.getenv("OPENAI_API_KEY"):
            st.info(
                "The AI API key is not configured yet. "
                "Set OPENAI_API_KEY in your environment and restart "
                "Streamlit to enable AI answers."
            )
        else:
            try:
                from openai import OpenAI

                client = OpenAI()
                with st.spinner("Generating explanation..."):
                    response = client.responses.create(
                        model="gpt-4o-mini",
                        instructions=(
                            "You are a beginner-friendly digital electronics "
                            "tutor. Explain ADCs and DACs clearly, using "
                            "simple examples, equations where useful, and "
                            "advantages and disadvantages. Distinguish "
                            "theory from results actually measured by a "
                            "Verilog simulation. Never claim that a "
                            "simulation was run unless its output is given."
                        ),
                        input=question
                    )

                st.markdown(response.output_text)

            except ImportError:
                st.error(
                    "Install the OpenAI Python package: pip install openai"
                )
            except Exception as exc:
                st.error(f"AI request failed: {exc}")

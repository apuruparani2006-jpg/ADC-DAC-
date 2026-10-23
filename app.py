import os
import io
import math
import shutil
import subprocess
import tempfile
from datetime import datetime

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

try:
    from google import genai
except ImportError:
    genai = None

st.set_page_config(page_title="ADC/DAC Simulator", page_icon="📡", layout="wide")
st.title("📡 ADC / DAC Simulator")
st.caption("Explore analog-to-digital conversion, digital-to-analog reconstruction, and mixed ADC → DAC workflows.")

# ----------------------------- Sidebar settings -----------------------------
st.sidebar.header("Simulation settings")
mode = st.sidebar.selectbox("Operating mode", ["ADC", "DAC", "ADC → DAC"])
bits = st.sidebar.slider("ADC/DAC resolution (bits)", min_value=2, max_value=16, value=8)
vref = st.sidebar.number_input("Reference voltage Vref (V)", min_value=0.1, max_value=100.0, value=5.0, step=0.1)
max_code = (1 << bits) - 1
st.sidebar.caption(f"Resolution: {bits} bits · Codes: 0–{max_code} · LSB: {vref / max_code:.6f} V")

# Always define manual input values so the AI Tutor can safely use them.
input_voltage = 1.25
digital_input = 64

if mode in ("ADC", "ADC → DAC"):
    input_voltage = st.sidebar.number_input(
        "Manual analog input voltage (V)", min_value=0.0, max_value=float(vref),
        value=min(1.25, float(vref)), step=0.05, format="%.4f"
    )
if mode == "DAC":
    digital_input = st.sidebar.number_input(
        "Manual digital input code", min_value=0, max_value=int(max_code),
        value=min(64, int(max_code)), step=1
    )

st.sidebar.divider()
st.sidebar.subheader("Waveform options")
waveform_type = st.sidebar.selectbox("Input waveform", ["Sine", "Square", "Triangle", "Sawtooth"])
frequency = st.sidebar.number_input("Waveform frequency (Hz)", min_value=0.1, max_value=10000.0, value=1.0, step=0.1)
sample_rate = st.sidebar.number_input("Sample rate (samples/s)", min_value=2.0, max_value=100000.0, value=100.0, step=1.0)
duration = st.sidebar.number_input("Duration (seconds)", min_value=0.1, max_value=20.0, value=2.0, step=0.1)
amplitude = st.sidebar.number_input("Waveform amplitude (V peak)", min_value=0.0, max_value=float(vref), value=min(2.0, float(vref)), step=0.1)
offset = st.sidebar.number_input("Waveform DC offset (V)", min_value=0.0, max_value=float(vref), value=float(vref) / 2, step=0.1)

# ----------------------------- Conversion helpers ---------------------------
def quantize_voltage(voltage, reference, resolution_bits):
    levels = (1 << resolution_bits) - 1
    clipped = np.clip(np.asarray(voltage, dtype=float), 0.0, reference)
    codes = np.rint(clipped / reference * levels).astype(int)
    reconstructed = codes / levels * reference
    return codes, reconstructed


def make_waveform(kind, times, freq, amp, dc):
    phase = (times * freq) % 1.0
    if kind == "Sine":
        values = dc + amp * np.sin(2 * np.pi * freq * times)
    elif kind == "Square":
        values = dc + amp * np.where(np.sin(2 * np.pi * freq * times) >= 0, 1.0, -1.0)
    elif kind == "Triangle":
        values = dc + amp * (2 * np.abs(2 * phase - 1) - 1)
    else:
        values = dc + amp * (2 * phase - 1)
    return np.clip(values, 0.0, vref)


def fig_line(x, y, name, title, x_title, y_title, y2=None, name2=None):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=x, y=y, mode="lines+markers", name=name))
    if y2 is not None:
        fig.add_trace(go.Scatter(x=x, y=y2, mode="lines", name=name2 or "Reconstructed"))
    fig.update_layout(title=title, xaxis_title=x_title, yaxis_title=y_title, hovermode="x unified", legend=dict(orientation="h"))
    return fig

# ----------------------------- Main simulation ------------------------------
st.header(f"{mode} operation")
if mode == "ADC":
    col1, col2, col3 = st.columns(3)
    adc_code = int(np.rint(input_voltage / vref * max_code))
    adc_code = int(np.clip(adc_code, 0, max_code))
    recon_voltage = adc_code / max_code * vref
    col1.metric("Analog input", f"{input_voltage:.4f} V")
    col2.metric("Digital output code", str(adc_code))
    col3.metric("Quantized voltage", f"{recon_voltage:.4f} V")
    st.write(f"Binary output ({bits} bits): `{format(adc_code, f'0{bits}b')}`")
    st.write(f"Quantization error: **{recon_voltage - input_voltage:+.6f} V**")
    st.progress(adc_code / max_code if max_code else 0)

elif mode == "DAC":
    dac_voltage = digital_input / max_code * vref
    col1, col2, col3 = st.columns(3)
    col1.metric("Digital input code", str(int(digital_input)))
    col2.metric("Binary input", format(int(digital_input), f"0{bits}b"))
    col3.metric("Analog output voltage", f"{dac_voltage:.4f} V")
    st.write(f"Normalized output: `{digital_input}/{max_code} × {vref:.4f} V` = **{dac_voltage:.6f} V**")
    codes = np.arange(max_code + 1)
    voltages = codes / max_code * vref
    fig = go.Figure(go.Scatter(x=codes, y=voltages, mode="lines", name="Ideal DAC transfer"))
    fig.add_trace(go.Scatter(x=[digital_input], y=[dac_voltage], mode="markers", marker=dict(size=12), name="Selected code"))
    fig.update_layout(title="Ideal DAC transfer characteristic", xaxis_title="Digital code", yaxis_title="Output voltage (V)")
    st.plotly_chart(fig, use_container_width=True)

else:
    adc_code = int(np.rint(input_voltage / vref * max_code))
    adc_code = int(np.clip(adc_code, 0, max_code))
    dac_voltage = adc_code / max_code * vref
    col1, col2, col3 = st.columns(3)
    col1.metric("Analog input", f"{input_voltage:.4f} V")
    col2.metric("ADC digital code", str(adc_code))
    col3.metric("DAC reconstructed voltage", f"{dac_voltage:.4f} V")
    st.write(f"Digital code in binary: `{format(adc_code, f'0{bits}b')}`")
    st.write(f"End-to-end error: **{dac_voltage - input_voltage:+.6f} V**")

st.divider()
st.header("Waveform simulation")
if st.button("Generate waveform and conversion results", type="primary"):
    n_samples = int(np.clip(math.floor(sample_rate * duration), 2, 20000))
    times = np.arange(n_samples) / sample_rate
    analog = make_waveform(waveform_type, times, frequency, amplitude, offset)
    codes, reconstructed = quantize_voltage(analog, vref, bits)
    df = pd.DataFrame({
        "time_s": times,
        "analog_input_V": analog,
        "digital_code": codes,
        "digital_binary": [format(int(c), f"0{bits}b") for c in codes],
        "reconstructed_output_V": reconstructed,
        "error_V": reconstructed - analog,
    })
    st.session_state["simulation_df"] = df
    st.session_state["simulation_meta"] = {"bits": bits, "vref": vref, "mode": mode, "waveform": waveform_type}

if "simulation_df" in st.session_state:
    df = st.session_state["simulation_df"]
    st.subheader("Analog input and reconstructed output")
    st.plotly_chart(fig_line(df["time_s"], df["analog_input_V"], "Analog input", "Input vs reconstructed waveform", "Time (s)", "Voltage (V)", df["reconstructed_output_V"], "Reconstructed output"), use_container_width=True)
    st.plotly_chart(fig_line(df["time_s"], df["digital_code"], "ADC code", "Quantized digital codes", "Time (s)", "Digital code"), use_container_width=True)
    st.plotly_chart(fig_line(df["time_s"], df["error_V"], "Quantization error", "Quantization error over time", "Time (s)", "Error (V)"), use_container_width=True)
    c1, c2, c3 = st.columns(3)
    c1.metric("Samples", f"{len(df):,}")
    c2.metric("Mean absolute error", f"{df['error_V'].abs().mean():.6f} V")
    c3.metric("Maximum absolute error", f"{df['error_V'].abs().max():.6f} V")
    st.dataframe(df.head(500), use_container_width=True)
    st.download_button("Download simulation CSV", data=df.to_csv(index=False).encode("utf-8"), file_name="adc_dac_simulation.csv", mime="text/csv")

st.divider()
st.header("Generated code examples")
code_tab1, code_tab2 = st.tabs(["8086 Assembly template", "Verilog RTL + testbench"])
with code_tab1:
    asm_code = f"""; ADC/DAC numeric conversion example template
; Resolution: {bits} bits, Vref: {vref:.4f} V, maximum code: {max_code}
; NOTE: This is a numeric demonstration template, not hardware-specific I/O code.

DATA SEGMENT
    DIGITAL_CODE DW {int(np.clip(round(input_voltage / vref * max_code), 0, max_code))}
    MAX_CODE     DW {max_code}
DATA ENDS

CODE SEGMENT
ASSUME CS:CODE, DS:DATA
START:
    MOV AX, DATA
    MOV DS, AX
    ; Replace DIGITAL_CODE with the value read from your ADC interface.
    ; Real ADC/DAC devices require device-specific I/O routines.
    MOV AX, DIGITAL_CODE
    ; Conversion relationship: Vout = code * Vref / MAX_CODE
    MOV AH, 4CH
    INT 21H
CODE ENDS
END START
"""
    st.code(asm_code, language="asm")
    st.download_button("Download 8086 template", data=asm_code, file_name="adc_dac_template.asm", mime="text/plain")
with code_tab2:
    verilog_code = f"""// Parameterized ideal ADC/DAC numeric model (simulation only)
module adc_dac_model #(parameter BITS = {bits}, parameter integer VREF_MV = {int(round(vref * 1000))}) (
    input  wire [BITS-1:0] digital_in,
    output wire [BITS-1:0] digital_out,
    output wire [31:0]     dac_millivolts
);
localparam integer MAX_CODE = (1 << BITS) - 1;
    assign digital_out = digital_in;
    assign dac_millivolts = (digital_in * VREF_MV) / MAX_CODE;
endmodule

module tb;
    localparam BITS = {bits};
    reg [BITS-1:0] digital_in;
    wire [BITS-1:0] digital_out;
    wire [31:0] dac_millivolts;
    adc_dac_model #(BITS, {int(round(vref * 1000))}) dut(digital_in, digital_out, dac_millivolts);
    initial begin
        digital_in = 0; #10;
        digital_in = (1 << BITS) / 4; #10;
        digital_in = (1 << BITS) / 2; #10;
        digital_in = (1 << BITS) - 1; #10;
        $display("code=%0d output=%0d mV", digital_in, dac_millivolts);
        $finish;
    end
endmodule
"""
    st.code(verilog_code, language="verilog")
    st.download_button("Download Verilog testbench", data=verilog_code, file_name="adc_dac_tb.v", mime="text/plain")
    if st.button("Run Verilog testbench (if Icarus Verilog is installed)"):
        if not shutil.which("iverilog") or not shutil.which("vvp"):
            st.warning("Icarus Verilog is not installed in this runtime. Install it in the Docker image to enable execution.")
        else:
            with tempfile.TemporaryDirectory() as tmpdir:
                source_path = os.path.join(tmpdir, "adc_dac_tb.v")
                output_path = os.path.join(tmpdir, "sim.out")
                with open(source_path, "w", encoding="utf-8") as source_file:
                    source_file.write(verilog_code)
                compile_result = subprocess.run(["iverilog", "-o", output_path, source_path], capture_output=True, text=True, timeout=15)
                if compile_result.returncode != 0:
                    st.error("Verilog compile failed")
                    st.code(compile_result.stderr or compile_result.stdout)
                else:
                    run_result = subprocess.run(["vvp", output_path], capture_output=True, text=True, timeout=15)
                    st.code(run_result.stdout or run_result.stderr)

# ----------------------------- Gemini AI Tutor ------------------------------
st.divider()
st.header("🤖 AI Tutor (Gemini)")
st.caption("Ask about ADC/DAC theory, quantization, binary codes, plots, or the generated examples.")

if "tutor_messages" not in st.session_state:
    st.session_state["tutor_messages"] = []

for message in st.session_state["tutor_messages"]:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

question = st.chat_input("Ask your AI Tutor a question...")
if question:
    st.session_state["tutor_messages"].append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    api_key = os.getenv("GEMINI_API_KEY")
    with st.chat_message("assistant"):
        if not api_key:
            answer = "Gemini API key is not configured. In Render, open your service → Environment and add GEMINI_API_KEY with your key, then redeploy."
            st.warning(answer)
        elif genai is None:
            answer = "The google-genai package is missing. Add google-genai to requirements.txt and redeploy."
            st.error(answer)
        else:
            try:
                client = genai.Client(api_key=api_key)
                context = (
                    "You are a helpful electronics tutor inside an ADC/DAC simulator. "
                    "Explain clearly for a student, use equations and short examples where useful, "
                    "and do not claim that a software model is real hardware.\n"
                    f"Current mode: {mode}. Resolution: {bits} bits. Vref: {vref} V. Maximum code: {max_code}.\n"
                )
                if mode in ("ADC", "ADC → DAC"):
                    code_now = int(np.clip(round(input_voltage / vref * max_code), 0, max_code))
                    context += f"Manual analog input: {input_voltage} V; corresponding ADC code: {code_now}; reconstructed voltage: {code_now / max_code * vref:.6f} V.\n"
                if mode == "DAC":
                    context += f"Manual digital input: {int(digital_input)}; DAC output: {int(digital_input) / max_code * vref:.6f} V.\n"
                if "simulation_df" in st.session_state:
                    sim_df = st.session_state["simulation_df"]
                    context += f"Waveform simulation exists with {len(sim_df)} samples and mean absolute quantization error {sim_df['error_V'].abs().mean():.6f} V.\n"
                history = "\n".join(
                    f"{m['role']}: {m['content']}" for m in st.session_state["tutor_messages"][-8:]
                )
                prompt = f"{context}\nRecent conversation:\n{history}\nuser: {question}\nassistant:"
                response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
                answer = (getattr(response, "text", None) or "Gemini returned an empty response. Please try again.").strip()
                st.markdown(answer)
            except Exception as exc:
                answer = "Gemini request failed. Check that your API key is valid, the model is available to your key, and your Gemini API quota is available."
                st.error(answer)
                # Detailed diagnostics are logged in Render logs, not exposed to the user.
                print(f"Gemini Tutor error: {type(exc).__name__}: {exc}")
    st.session_state["tutor_messages"].append({"role": "assistant", "content": answer})

if st.button("Clear AI Tutor conversation"):
    st.session_state["tutor_messages"] = []
    st.rerun()

st.caption("Educational simulator only. Idealized calculations do not model all real converter hardware effects.")


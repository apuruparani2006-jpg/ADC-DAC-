`timescale 1ns/1ps

module dac_tb;

reg [3:0] digital_in;
    wire [15:0] vout_mv;

dac uut (
        .digital_in(digital_in),
        .vout_mv(vout_mv)
    );

    integer i;

initial begin
        $dumpfile("dac_wave.vcd");
        $dumpvars(0, dac_tb);

$display("DAC RESULTS");
        $display("Digital_Code,Voltage_mV");

        for (i = 0; i <16; i = i + 1) begin
            digital_in = i;
            #10;
            $display("%0d,%0d", digital_in, vout_mv);
        end

$finish;
    end

endmodule

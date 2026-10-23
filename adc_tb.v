
`timescale 1ns/1ps

module adc_tb;

    reg [15:0] vin_mv;
    wire [3:0] digital_out;

    adc uut (
        .vin_mv(vin_mv),
        .digital_out(digital_out)
    );

    integer i;

    initial begin
        $dumpfile("adc_wave.vcd");
        $dumpvars(0, adc_tb);

        $display("ADC RESULTS");
        $display("Voltage_mV,Digital_Code");

        vin_mv = 0;
        #10;
        $display("%0d,%0d", vin_mv, digital_out);

        vin_mv = 500;
        #10;
        $display("%0d,%0d", vin_mv, digital_out);

        vin_mv = 1000;
        #10;
        $display("%0d,%0d", vin_mv, digital_out);

        vin_mv = 1650;
        #10;
        $display("%0d,%0d", vin_mv, digital_out);

        vin_mv = 2500;
        #10;
        $display("%0d,%0d", vin_mv, digital_out);

        vin_mv = 3300;
        #10;
        $display("%0d,%0d", vin_mv, digital_out);

        $finish;
    end

endmodule

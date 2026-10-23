
`timescale 1ns/1ps

module tb_adc #(
    parameter integer BITS = 8,
    parameter integer VREF_MV = 5000
);

    reg [31:0] voltage_mv;
    wire [BITS-1:0] digital_code;

    integer input_file;
    integer scan_status;

    adc #(
        .BITS(BITS),
        .VREF_MV(VREF_MV)
    ) dut (
        .voltage_mv(voltage_mv),
        .digital_code(digital_code)
    );

    initial begin
        input_file = $fopen("adc_inputs.txt", "r");

        if (input_file == 0) begin
            $display("ERROR: Cannot open adc_inputs.txt");
            $finish;
        end

        while (!$feof(input_file)) begin
            scan_status = $fscanf(input_file, "%d", voltage_mv);

            if (scan_status == 1) begin
                #1;
                $display("ADC_RESULT %0d %0d",
                         voltage_mv, digital_code);
            end
        end

        $fclose(input_file);
        $finish;
    end

endmodule


`timescale 1ns/1ps

module tb_dac #(
    parameter integer BITS = 8,
    parameter integer VREF_MV = 5000
);

reg [BITS-1:0] digital_code;
    wire [31:0] voltage_mv;

integer input_file;
    integer scan_status;
    integer input_code;

dac #(
        .BITS(BITS),
        .VREF_MV(VREF_MV)
    ) dut (
        .digital_code(digital_code),
        .voltage_mv(voltage_mv)
    );

initial begin
        input_file = $fopen("dac_inputs.txt", "r");

if (input_file == 0) begin
            $display("ERROR: Cannot open dac_inputs.txt");
            $finish;
        end

while (!$feof(input_file)) begin
            scan_status = $fscanf(input_file, "%d", input_code);

if (scan_status == 1) begin
                digital_code = input_code;
                #1;
                $display("DAC_RESULT %0d %0d",
                         input_code, voltage_mv);
            end
        end

$fclose(input_file);
        $finish;
    end

endmodule

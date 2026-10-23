`timescale 1ns/1ps

module tb_dac;

    reg  [9:0]  digital_code;
    wire [15:0] voltage_mv;

    integer input_file;
    integer scan_status;

    dac #(
        .BITS(10),
        .VREF_MV(5000)
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

        $display("Digital Code | Voltage(mV)");
        $display("--------------------------");

        while (!$feof(input_file)) begin
            scan_status = $fscanf(input_file, "%d\n", digital_code);

            if (scan_status == 1) begin
                #10;
                $display("%d | %d", digital_code, voltage_mv);
            end
        end

        $fclose(input_file);
        $finish;
    end

endmodule

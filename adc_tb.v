`timescale 1ns/1ps

module tb_adc;

    reg  [15:0] voltage_mv;
    wire [9:0]  digital_code;

    integer input_file;
    integer scan_status;

    adc #(
        .BITS(10),
        .VREF_MV(5000)
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

        $display("Voltage(mV) | Digital Code");
        $display("--------------------------");

        while (!$feof(input_file)) begin
            scan_status = $fscanf(input_file, "%d\n", voltage_mv);

            if (scan_status == 1) begin
                #10;
                $display("%d | %d", voltage_mv, digital_code);
            end
        end

        $fclose(input_file);
        $finish;
    end

endmodule

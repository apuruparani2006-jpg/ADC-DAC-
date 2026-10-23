`timescale 1ns/1ps

module adc #(
    parameter integer BITS = 8,
    parameter integer VREF_MV = 5000
)(
    input  wire [31:0] voltage_mv,
    output reg  [BITS-1:0] digital_code
);

    integer max_code;
    integer scaled_code;

    always @(*) begin
        max_code = (1 << BITS) - 1;

        if (voltage_mv >= VREF_MV) begin
            digital_code = max_code;
        end
        else begin
            scaled_code =
                (voltage_mv * max_code + VREF_MV / 2)
                / VREF_MV;

            digital_code = scaled_code;
        end
    end

endmodule


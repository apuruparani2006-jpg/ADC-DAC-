
`timescale 1ns/1ps

module dac #(
    parameter integer BITS = 8,
    parameter integer VREF_MV = 5000
)(
    input  wire [BITS-1:0] digital_code,
    output reg  [31:0] voltage_mv
);

    integer max_code;

    always @(*) begin
        max_code = (1 << BITS) - 1;

        voltage_mv =
            (digital_code * VREF_MV + max_code / 2)
            / max_code;
    end

endmodule

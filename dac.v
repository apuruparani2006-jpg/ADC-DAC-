module dac #(
    parameter BITS = 10,
    parameter VREF_MV = 5000
)(
    input  wire [BITS-1:0] digital_code,
    output reg  [15:0] voltage_mv
);

    integer max_code;

    always @(*) begin
        max_code = (1 << BITS) - 1;
        voltage_mv = (digital_code * VREF_MV) / max_code;
    end

endmodule

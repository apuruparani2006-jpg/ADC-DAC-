module adc #(
    parameter BITS = 10,
    parameter VREF_MV = 5000
)(
    input  wire [15:0] voltage_mv,
    output reg  [BITS-1:0] digital_code
);

    integer code_calc;
    integer max_code;

    always @(*) begin
        max_code = (1 << BITS) - 1;

        if (voltage_mv >= VREF_MV)
            digital_code = max_code;
        else
            digital_code =
                (voltage_mv * max_code) / VREF_MV;
    end

endmodule

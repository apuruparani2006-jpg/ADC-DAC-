
module adc (
    input  [15:0] vin_mv,
    output reg [3:0] digital_out
);

    integer temp_code;

    always @(*) begin
        // Map 0–3300 mV to a 4-bit digital code
        temp_code = (vin_mv * 16) / 3300;

        // Saturate at the maximum 4-bit code
        if (vin_mv >= 3300)
            digital_out = 4'd15;
        else if (temp_code > 15)
            digital_out = 4'd15;
        else
            digital_out = temp_code[3:0];
    end

endmodule

module dac (
    input  [3:0] digital_in,
    output reg [15:0] vout_mv
);

always @(*) begin
        // Convert digital code to millivolts
        vout_mv = (digital_in * 3300) / 15;
    end

endmodule

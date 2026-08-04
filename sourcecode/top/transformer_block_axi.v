`timescale 1 ns / 1 ps

// AXI4-Lite + dual AXI4-Stream-slave + AXI4-Stream-master wrapper around
// transformer_block_top (the full MM_ultra -> Softmax_control -> EightGelus
// pipeline), mirroring the structure of MM_ultra_axi.v/MM_ultra_top.v (the
// existing wrapper around MM_ultra alone) but sized for the full pipeline's
// larger config surface and its output stream's 'keep' signal.
//
// Deliberate deviation from MM_ultra_axi.v's convention: user parameters
// here keep transformer_block_top.v's own names (A_size, Weight_Block_num,
// ...) instead of inventing lowercase aliases (array_size, ...) the way
// MM_ultra_axi.v did. That renaming is exactly what caused the
// array_size/A_size default drift documented in project_story.md (Sections
// 15-16) -- avoiding a second instance of the same class of bug by keeping
// one name per concept.
//
// Register map (C_S_AXI_ADDR_WIDTH=5 -> 8 word registers, addr[4:2] select):
//   0  mm_shift_in             (RW)
//   1  mm_F_length_in          (RW)
//   2  mm_F_width_block_num_in (RW)
//   3  mm_W_width_block_num_in (RW)
//   4  softmax_scale_in        (RW, signed)
//   5  softmax_scale_out       (RW)
//   6  gelu_scale              (RW)
//   7  status: bit0 = softmax_to_gelu_fifo_overflow (RO, live, not latched)

module transformer_block_axi #
(
	// Users to add parameters here -- same names/defaults as
	// transformer_block_top.v itself; see header note above.
    parameter integer     A_size                     = 16,
    parameter integer     data_width                 = 8,
    parameter integer     shift_width                = 10,
    parameter integer     Weight_Block_num           = 2400,
    parameter integer     IN_Feature_Block_num       = 2400,
    parameter integer     OUT_Feature_Block_num      = 2400,
    parameter integer     OUT_MEM_WIDTH              = 21,
    parameter integer     F_length_width             = 10,
    parameter integer     F_width_block_num_width    = 5,
    parameter integer     W_width_block_num_width    = 5,
    parameter integer     num_gelu                   = 4,
    parameter integer     GELU_FIFO_DEPTH            = 512,

	// User parameters ends
	// Do not modify the parameters beyond this line

	// Width of S_AXI data bus
	parameter integer C_S_AXI_DATA_WIDTH	= 32,
	// Width of S_AXI address bus
	parameter integer C_S_AXI_ADDR_WIDTH	= 5
)
(
	// Users to add ports here
    input                                    axis_aclk,
    input                                    aresetn,

    input  [A_size*data_width-1:0]           s0_axis_tdata,
    input                                     s0_axis_tvalid,
    output                                    s0_axis_tready,
    input                                     s0_axis_tlast,

    input  [A_size*data_width-1:0]           s1_axis_tdata,
    input                                     s1_axis_tvalid,
    output                                    s1_axis_tready,
    input                                     s1_axis_tlast,

    output [num_gelu*data_width-1:0]         m0_axis_tdata,
    output                                    m0_axis_tvalid,
    input                                     m0_axis_tready,
    output                                    m0_axis_tlast,
    output [num_gelu-1:0]                    m0_axis_tkeep,
	// User ports ends
	// Do not modify the ports beyond this line

	// Global Clock Signal
	input wire  S_AXI_ACLK,
	// Global Reset Signal. This Signal is Active LOW
	input wire  S_AXI_ARESETN,
	// Write address (issued by master, acceped by Slave)
	input wire [C_S_AXI_ADDR_WIDTH-1 : 0] S_AXI_AWADDR,
	// Write channel Protection type.
	input wire [2 : 0] S_AXI_AWPROT,
	// Write address valid.
	input wire  S_AXI_AWVALID,
	// Write address ready.
	output wire  S_AXI_AWREADY,
	// Write data (issued by master, acceped by Slave)
	input wire [C_S_AXI_DATA_WIDTH-1 : 0] S_AXI_WDATA,
	// Write strobes.
	input wire [(C_S_AXI_DATA_WIDTH/8)-1 : 0] S_AXI_WSTRB,
	// Write valid.
	input wire  S_AXI_WVALID,
	// Write ready.
	output wire  S_AXI_WREADY,
	// Write response.
	output wire [1 : 0] S_AXI_BRESP,
	// Write response valid.
	output wire  S_AXI_BVALID,
	// Response ready.
	input wire  S_AXI_BREADY,
	// Read address (issued by master, acceped by Slave)
	input wire [C_S_AXI_ADDR_WIDTH-1 : 0] S_AXI_ARADDR,
	// Protection type.
	input wire [2 : 0] S_AXI_ARPROT,
	// Read address valid.
	input wire  S_AXI_ARVALID,
	// Read address ready.
	output wire  S_AXI_ARREADY,
	// Read data (issued by slave)
	output wire [C_S_AXI_DATA_WIDTH-1 : 0] S_AXI_RDATA,
	// Read response.
	output wire [1 : 0] S_AXI_RRESP,
	// Read valid.
	output wire  S_AXI_RVALID,
	// Read ready.
	input wire  S_AXI_RREADY
);

// AXI4LITE signals
reg [C_S_AXI_ADDR_WIDTH-1 : 0] 	axi_awaddr;
reg  	axi_awready;
reg  	axi_wready;
reg [1 : 0] 	axi_bresp;
reg  	axi_bvalid;
reg [C_S_AXI_ADDR_WIDTH-1 : 0] 	axi_araddr;
reg  	axi_arready;
reg [C_S_AXI_DATA_WIDTH-1 : 0] 	axi_rdata;
reg [1 : 0] 	axi_rresp;
reg  	axi_rvalid;

// Example-specific design signals
// local parameter for addressing 32 bit / 64 bit C_S_AXI_DATA_WIDTH
// ADDR_LSB is used for addressing 32/64 bit registers/memories
// ADDR_LSB = 2 for 32 bits (n downto 2)
localparam integer ADDR_LSB = (C_S_AXI_DATA_WIDTH/32) + 1;
// 3 index bits -> 8 word registers (0-7), vs MM_ultra_axi.v's 2 bits/4 regs
localparam integer OPT_MEM_ADDR_BITS = 2;
//----------------------------------------------
//-- Signals for user logic register space
//-- Number of Slave Registers 8 (7 read-write config + 1 read-only status)
//------------------------------------------------
reg [C_S_AXI_DATA_WIDTH-1:0]	slv_reg0;
reg [C_S_AXI_DATA_WIDTH-1:0]	slv_reg1;
reg [C_S_AXI_DATA_WIDTH-1:0]	slv_reg2;
reg [C_S_AXI_DATA_WIDTH-1:0]	slv_reg3;
reg [C_S_AXI_DATA_WIDTH-1:0]	slv_reg4;
reg [C_S_AXI_DATA_WIDTH-1:0]	slv_reg5;
reg [C_S_AXI_DATA_WIDTH-1:0]	slv_reg6;
// slv_reg7 intentionally not backed by storage -- address 7 is the
// read-only status register, driven live from softmax_to_gelu_fifo_overflow
// in the read mux below, and ignored on write.
wire	 slv_reg_rden;
wire	 slv_reg_wren;
reg [C_S_AXI_DATA_WIDTH-1:0]	 reg_data_out;
integer	 byte_index;
reg	 aw_en;

wire softmax_to_gelu_fifo_overflow;

// I/O Connections assignments

assign S_AXI_AWREADY	= axi_awready;
assign S_AXI_WREADY	= axi_wready;
assign S_AXI_BRESP	= axi_bresp;
assign S_AXI_BVALID	= axi_bvalid;
assign S_AXI_ARREADY	= axi_arready;
assign S_AXI_RDATA	= axi_rdata;
assign S_AXI_RRESP	= axi_rresp;
assign S_AXI_RVALID	= axi_rvalid;
// Implement axi_awready generation
// axi_awready is asserted for one S_AXI_ACLK clock cycle when both
// S_AXI_AWVALID and S_AXI_WVALID are asserted. axi_awready is
// de-asserted when reset is low.

always @( posedge S_AXI_ACLK )
begin
  if ( S_AXI_ARESETN == 1'b0 )
    begin
      axi_awready <= 1'b0;
      aw_en <= 1'b1;
    end
  else
    begin
      if (~axi_awready && S_AXI_AWVALID && S_AXI_WVALID && aw_en)
        begin
          axi_awready <= 1'b1;
          aw_en <= 1'b0;
        end
        else if (S_AXI_BREADY && axi_bvalid)
            begin
              aw_en <= 1'b1;
              axi_awready <= 1'b0;
            end
      else
        begin
          axi_awready <= 1'b0;
        end
    end
end

// Implement axi_awaddr latching

always @( posedge S_AXI_ACLK )
begin
  if ( S_AXI_ARESETN == 1'b0 )
    begin
      axi_awaddr <= 0;
    end
  else
    begin
      if (~axi_awready && S_AXI_AWVALID && S_AXI_WVALID && aw_en)
        begin
          axi_awaddr <= S_AXI_AWADDR;
        end
    end
end

// Implement axi_wready generation

always @( posedge S_AXI_ACLK )
begin
  if ( S_AXI_ARESETN == 1'b0 )
    begin
      axi_wready <= 1'b0;
    end
  else
    begin
      if (~axi_wready && S_AXI_WVALID && S_AXI_AWVALID && aw_en )
        begin
          axi_wready <= 1'b1;
        end
      else
        begin
          axi_wready <= 1'b0;
        end
    end
end

// Implement memory mapped register select and write logic generation
assign slv_reg_wren = axi_wready && S_AXI_WVALID && axi_awready && S_AXI_AWVALID;

always @( posedge S_AXI_ACLK )
begin
  if ( S_AXI_ARESETN == 1'b0 )
    begin
      slv_reg0 <= 0;
      slv_reg1 <= 0;
      slv_reg2 <= 0;
      slv_reg3 <= 0;
      slv_reg4 <= 0;
      slv_reg5 <= 0;
      slv_reg6 <= 0;
    end
  else begin
    if (slv_reg_wren)
      begin
        case ( axi_awaddr[ADDR_LSB+OPT_MEM_ADDR_BITS:ADDR_LSB] )
          3'h0:
            for ( byte_index = 0; byte_index <= (C_S_AXI_DATA_WIDTH/8)-1; byte_index = byte_index+1 )
              if ( S_AXI_WSTRB[byte_index] == 1 ) begin
                slv_reg0[(byte_index*8) +: 8] <= S_AXI_WDATA[(byte_index*8) +: 8];
              end
          3'h1:
            for ( byte_index = 0; byte_index <= (C_S_AXI_DATA_WIDTH/8)-1; byte_index = byte_index+1 )
              if ( S_AXI_WSTRB[byte_index] == 1 ) begin
                slv_reg1[(byte_index*8) +: 8] <= S_AXI_WDATA[(byte_index*8) +: 8];
              end
          3'h2:
            for ( byte_index = 0; byte_index <= (C_S_AXI_DATA_WIDTH/8)-1; byte_index = byte_index+1 )
              if ( S_AXI_WSTRB[byte_index] == 1 ) begin
                slv_reg2[(byte_index*8) +: 8] <= S_AXI_WDATA[(byte_index*8) +: 8];
              end
          3'h3:
            for ( byte_index = 0; byte_index <= (C_S_AXI_DATA_WIDTH/8)-1; byte_index = byte_index+1 )
              if ( S_AXI_WSTRB[byte_index] == 1 ) begin
                slv_reg3[(byte_index*8) +: 8] <= S_AXI_WDATA[(byte_index*8) +: 8];
              end
          3'h4:
            for ( byte_index = 0; byte_index <= (C_S_AXI_DATA_WIDTH/8)-1; byte_index = byte_index+1 )
              if ( S_AXI_WSTRB[byte_index] == 1 ) begin
                slv_reg4[(byte_index*8) +: 8] <= S_AXI_WDATA[(byte_index*8) +: 8];
              end
          3'h5:
            for ( byte_index = 0; byte_index <= (C_S_AXI_DATA_WIDTH/8)-1; byte_index = byte_index+1 )
              if ( S_AXI_WSTRB[byte_index] == 1 ) begin
                slv_reg5[(byte_index*8) +: 8] <= S_AXI_WDATA[(byte_index*8) +: 8];
              end
          3'h6:
            for ( byte_index = 0; byte_index <= (C_S_AXI_DATA_WIDTH/8)-1; byte_index = byte_index+1 )
              if ( S_AXI_WSTRB[byte_index] == 1 ) begin
                slv_reg6[(byte_index*8) +: 8] <= S_AXI_WDATA[(byte_index*8) +: 8];
              end
          default : begin
                      slv_reg0 <= slv_reg0;
                      slv_reg1 <= slv_reg1;
                      slv_reg2 <= slv_reg2;
                      slv_reg3 <= slv_reg3;
                      slv_reg4 <= slv_reg4;
                      slv_reg5 <= slv_reg5;
                      slv_reg6 <= slv_reg6;
                      // 3'h7 (status) and any out-of-range address: no-op,
                      // matches address 7 being read-only.
                    end
        endcase
      end
  end
end

// Implement write response logic generation

always @( posedge S_AXI_ACLK )
begin
  if ( S_AXI_ARESETN == 1'b0 )
    begin
      axi_bvalid  <= 0;
      axi_bresp   <= 2'b0;
    end
  else
    begin
      if (axi_awready && S_AXI_AWVALID && ~axi_bvalid && axi_wready && S_AXI_WVALID)
        begin
          axi_bvalid <= 1'b1;
          axi_bresp  <= 2'b0; // 'OKAY' response
        end
      else
        begin
          if (S_AXI_BREADY && axi_bvalid)
            begin
              axi_bvalid <= 1'b0;
            end
        end
    end
end

// Implement axi_arready generation

always @( posedge S_AXI_ACLK )
begin
  if ( S_AXI_ARESETN == 1'b0 )
    begin
      axi_arready <= 1'b0;
      axi_araddr  <= 32'b0;
    end
  else
    begin
      if (~axi_arready && S_AXI_ARVALID)
        begin
          axi_arready <= 1'b1;
          axi_araddr  <= S_AXI_ARADDR;
        end
      else
        begin
          axi_arready <= 1'b0;
        end
    end
end

// Implement axi_arvalid generation

always @( posedge S_AXI_ACLK )
begin
  if ( S_AXI_ARESETN == 1'b0 )
    begin
      axi_rvalid <= 0;
      axi_rresp  <= 0;
    end
  else
    begin
      if (axi_arready && S_AXI_ARVALID && ~axi_rvalid)
        begin
          axi_rvalid <= 1'b1;
          axi_rresp  <= 2'b0; // 'OKAY' response
        end
      else if (axi_rvalid && S_AXI_RREADY)
        begin
          axi_rvalid <= 1'b0;
        end
    end
end

// Implement memory mapped register select and read logic generation
assign slv_reg_rden = axi_arready & S_AXI_ARVALID & ~axi_rvalid;
always @(*)
begin
      case ( axi_araddr[ADDR_LSB+OPT_MEM_ADDR_BITS:ADDR_LSB] )
        3'h0   : reg_data_out <= slv_reg0;
        3'h1   : reg_data_out <= slv_reg1;
        3'h2   : reg_data_out <= slv_reg2;
        3'h3   : reg_data_out <= slv_reg3;
        3'h4   : reg_data_out <= slv_reg4;
        3'h5   : reg_data_out <= slv_reg5;
        3'h6   : reg_data_out <= slv_reg6;
        3'h7   : reg_data_out <= {{(C_S_AXI_DATA_WIDTH-1){1'b0}}, softmax_to_gelu_fifo_overflow};
        default : reg_data_out <= 0;
      endcase
end

// Output register or memory read data
always @( posedge S_AXI_ACLK )
begin
  if ( S_AXI_ARESETN == 1'b0 )
    begin
      axi_rdata  <= 0;
    end
  else
    begin
      if (slv_reg_rden)
        begin
          axi_rdata <= reg_data_out;     // register read data
        end
    end
end

// Add user logic here
transformer_block_top
#(
    .A_size(A_size),
    .data_width(data_width),
    .shift_width(shift_width),
    .Weight_Block_num(Weight_Block_num),
    .IN_Feature_Block_num(IN_Feature_Block_num),
    .OUT_Feature_Block_num(OUT_Feature_Block_num),
    .OUT_MEM_WIDTH(OUT_MEM_WIDTH),
    .F_length_width(F_length_width),
    .F_width_block_num_width(F_width_block_num_width),
    .W_width_block_num_width(W_width_block_num_width),
    .num_gelu(num_gelu),
    .GELU_FIFO_DEPTH(GELU_FIFO_DEPTH)
) u_transformer_block_top (
    .clk(axis_aclk),
    .rst_n(aresetn),

    .mm_shift_in(slv_reg0),
    .mm_F_length_in(slv_reg1),
    .mm_F_width_block_num_in(slv_reg2),
    .mm_W_width_block_num_in(slv_reg3),

    .mm_in_F_valid(s0_axis_tvalid),
    .mm_in_F_last(s0_axis_tlast),
    .mm_in_F_ready(s0_axis_tready),
    .mm_in_F_data(s0_axis_tdata),

    .mm_in_W_valid(s1_axis_tvalid),
    .mm_in_W_last(s1_axis_tlast),
    .mm_in_W_ready(s1_axis_tready),
    .mm_in_W_data(s1_axis_tdata),

    .softmax_scale_in(slv_reg4),
    .softmax_scale_out(slv_reg5),

    .gelu_scale(slv_reg6),

    .out_valid(m0_axis_tvalid),
    .out_ready(m0_axis_tready),
    .out_last(m0_axis_tlast),
    .out_data(m0_axis_tdata),
    .out_keep(m0_axis_tkeep),

    .softmax_to_gelu_fifo_overflow(softmax_to_gelu_fifo_overflow)
);

// User logic ends
endmodule

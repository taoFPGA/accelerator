`timescale 1ns / 1ps

// Outer port-list wrapper around transformer_block_axi -- mirrors
// MM_ultra_top.v's structure (the equivalent wrapper for MM_ultra alone),
// sized for the full pipeline. See transformer_block_axi.v's header for the
// register map and the parameter-naming rationale.

module transformer_block_axi_top #
	(
		// Users to add parameters here -- same names/defaults as
		// transformer_block_top.v itself.
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

		// Parameters of Axi Slave Bus Interface S00_AXI
		localparam integer C_S00_AXI_DATA_WIDTH	= 32,
		// 5 bits -> 8 word registers (see transformer_block_axi.v's map)
		localparam integer C_S00_AXI_ADDR_WIDTH	= 5
	)
	(
		// Users to add ports here
		input 										aclk,
    	input 										aresetn,

    	input [A_size*data_width-1:0] 	            s0_axis_tdata,
    	input       								s0_axis_tvalid,
    	output      								s0_axis_tready,
    	input       								s0_axis_tlast,

    	input [A_size*data_width-1:0] 	            s1_axis_tdata,
    	input       								s1_axis_tvalid,
    	output      								s1_axis_tready,
    	input       								s1_axis_tlast,

    	output [num_gelu*data_width-1:0] 	        m0_axis_tdata,
    	output       								m0_axis_tvalid,
    	input        								m0_axis_tready,
    	output      			 					m0_axis_tlast,
    	output [num_gelu-1:0]                      m0_axis_tkeep,
		// User ports ends
		// Do not modify the ports beyond this line

		// Ports of Axi Slave Bus Interface S00_AXI
		input wire [C_S00_AXI_ADDR_WIDTH-1 : 0] s00_axi_awaddr,
		input wire [2 : 0] s00_axi_awprot,
		input wire  s00_axi_awvalid,
		output wire  s00_axi_awready,
		input wire [C_S00_AXI_DATA_WIDTH-1 : 0] s00_axi_wdata,
		input wire [(C_S00_AXI_DATA_WIDTH/8)-1 : 0] s00_axi_wstrb,
		input wire  s00_axi_wvalid,
		output wire  s00_axi_wready,
		output wire [1 : 0] s00_axi_bresp,
		output wire  s00_axi_bvalid,
		input wire  s00_axi_bready,
		input wire [C_S00_AXI_ADDR_WIDTH-1 : 0] s00_axi_araddr,
		input wire [2 : 0] s00_axi_arprot,
		input wire  s00_axi_arvalid,
		output wire  s00_axi_arready,
		output wire [C_S00_AXI_DATA_WIDTH-1 : 0] s00_axi_rdata,
		output wire [1 : 0] s00_axi_rresp,
		output wire  s00_axi_rvalid,
		input wire  s00_axi_rready
	);
// Instantiation of Axi Bus Interface S00_AXI
	transformer_block_axi # (
		.C_S_AXI_DATA_WIDTH(C_S00_AXI_DATA_WIDTH),
		.C_S_AXI_ADDR_WIDTH(C_S00_AXI_ADDR_WIDTH),

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
	) U_transformer_block_axi (
		.S_AXI_ACLK(aclk),
		.S_AXI_ARESETN(aresetn),
		.S_AXI_AWADDR(s00_axi_awaddr),
		.S_AXI_AWPROT(s00_axi_awprot),
		.S_AXI_AWVALID(s00_axi_awvalid),
		.S_AXI_AWREADY(s00_axi_awready),
		.S_AXI_WDATA(s00_axi_wdata),
		.S_AXI_WSTRB(s00_axi_wstrb),
		.S_AXI_WVALID(s00_axi_wvalid),
		.S_AXI_WREADY(s00_axi_wready),
		.S_AXI_BRESP(s00_axi_bresp),
		.S_AXI_BVALID(s00_axi_bvalid),
		.S_AXI_BREADY(s00_axi_bready),
		.S_AXI_ARADDR(s00_axi_araddr),
		.S_AXI_ARPROT(s00_axi_arprot),
		.S_AXI_ARVALID(s00_axi_arvalid),
		.S_AXI_ARREADY(s00_axi_arready),
		.S_AXI_RDATA(s00_axi_rdata),
		.S_AXI_RRESP(s00_axi_rresp),
		.S_AXI_RVALID(s00_axi_rvalid),
		.S_AXI_RREADY(s00_axi_rready),

		.axis_aclk(aclk),
		.aresetn(aresetn),

		.s0_axis_tdata(s0_axis_tdata),
		.s0_axis_tvalid(s0_axis_tvalid),
		.s0_axis_tready(s0_axis_tready),
		.s0_axis_tlast(s0_axis_tlast),

		.s1_axis_tdata(s1_axis_tdata),
		.s1_axis_tvalid(s1_axis_tvalid),
		.s1_axis_tready(s1_axis_tready),
		.s1_axis_tlast(s1_axis_tlast),

		.m0_axis_tdata(m0_axis_tdata),
		.m0_axis_tvalid(m0_axis_tvalid),
		.m0_axis_tready(m0_axis_tready),
		.m0_axis_tlast(m0_axis_tlast),
		.m0_axis_tkeep(m0_axis_tkeep)
	);

	// Add user logic here

	// User logic ends

	endmodule

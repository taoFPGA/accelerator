# =============================================================================
# dump_arch.tcl  --  Extract the architectural "ground truth" of the taoFPGA
#                    accelerator from a Vivado checkpoint into architecture_data.json
#
# Produces, for the chosen hierarchy scope:
#   * full module hierarchy tree (path / ref / parent / depth / children)
#   * per-module resource utilisation (LUT / FF / DSP / BRAM / URAM / CARRY / SRL),
#     both inclusive (rolled up) and exclusive (own logic only)
#   * clock-domain membership per module (FF count per clock) + CDC edge flags
#   * registered-output ratio per boundary module (pipeline-boundary signal)
#   * module-to-module port/bus connectivity graph (AXI / AXI-Stream aware)
#   * placement footprint per module: SLICE X/Y bounding box + clock-region
#     histogram (+ SLR histogram; trivial on single-die 7-series)
#   * pblock / floorplan ranges if present
#   * a Graphviz dataflow.dot of the connectivity graph (bonus)
#   * plain-text Vivado cross-check reports alongside the JSON
#
# Usage:
#   vivado -mode batch -notrace -source scripts/dump_arch.tcl -tclargs \
#       dcp=<path/to/checkpoint.dcp> \
#       scope=<top-level accelerator instance, or empty for whole design> \
#       out=exports/architecture_data.json \
#       conn_depth=2
#
# All -tclargs are key=value and optional; sensible defaults below.
# =============================================================================

set SCRIPT_VERSION "1.0"

# ----------------------------------------------------------------------------
# 0. Argument parsing (key=value tokens in $argv)
# ----------------------------------------------------------------------------
array set OPT {
    dcp            ""
    scope          ""
    out            "exports/architecture_data.json"
    outdir         ""
    conn_depth     2
    max_uniq_sites 20000
    include_glue   0
    drop_ctrl_nets 1
    collapse_ports 1
}
foreach tok $argv {
    if {[regexp {^([a-zA-Z_]+)=(.*)$} $tok -> k v]} {
        if {[info exists OPT($k)]} {
            set OPT($k) $v
        } else {
            puts "WARNING: unknown arg '$k' ignored"
        }
    }
}

# Auto-locate a routed checkpoint if none given. scripts/soc_build/post_route.dcp
# is preferred: it is the checkpoint behind exports/design.bit (full transformer,
# transformer_block_axi_top). The workspace/ impl_1 checkpoints are an older
# matmul-only iteration (design_1 with MM_ultra_top) -- keep them as fallbacks.
if {$OPT(dcp) eq ""} {
    set candidates {
        scripts/soc_build/post_route.dcp
        scripts/soc_build/post_place.dcp
        dbs/design_1_wrapper_post_route_dspfix.dcp
        workspace/myproj/project_1.runs/impl_1/design_1_wrapper_routed.dcp
        workspace/myproj/project_1.runs/impl_1/design_1_wrapper_postroute_physopt.dcp
        workspace/myproj/project_1.runs/impl_1/design_1_wrapper_placed.dcp
        workspace/myproj/project_1.runs/impl_1/design_1_wrapper_opt.dcp
        workspace/myproj/project_1.runs/synth_1/design_1_wrapper.dcp
    }
    foreach c $candidates {
        if {[file exists $c]} { set OPT(dcp) $c ; break }
    }
}
if {$OPT(dcp) eq "" || ![file exists $OPT(dcp)]} {
    puts stderr "ERROR: no checkpoint found. Pass dcp=<path/to/x.dcp>"
    exit 2
}
if {$OPT(outdir) eq ""} {
    # derive from the JSON basename so parallel runs (system / accel / ...) don't
    # clobber each other's report directory
    set OPT(outdir) [file join [file dirname $OPT(out)] \
        "arch_dump_[file rootname [file tail $OPT(out)]]"]
}
file mkdir [file dirname $OPT(out)]
file mkdir $OPT(outdir)

set T0 [clock seconds]
proc note {msg} {
    global T0
    puts [format {[dump_arch +%4ds] %s} [expr {[clock seconds]-$T0}] $msg]
    flush stdout
}

# ----------------------------------------------------------------------------
# 1. Minimal tagged-value JSON emitter
#    value = {str X} | {num X} | {bool 0|1} | {null} | {arr {tagged...}} | {obj {k v k v...}}
# ----------------------------------------------------------------------------
namespace eval J {
    proc str  {s} { return [list str  $s] }
    proc num  {n} {
        if {$n eq "" || ![string is double -strict $n]} { return [list str $n] }
        return [list num $n]
    }
    proc bool {b} { return [list bool [expr {$b ? 1 : 0}]] }
    proc null {}  { return [list null {}] }
    proc arr  {items} { return [list arr $items] }
    proc obj  {args} { return [list obj $args] }

    proc esc {s} {
        set s [string map [list \\ \\\\ \" \\\" \b \\b \f \\f \n \\n \r \\r \t \\t] $s]
        regsub -all {[\x00-\x1f]} $s {} s
        return $s
    }
    proc dump {node {ind 0}} {
        lassign $node tag val
        set pad  [string repeat "  " $ind]
        set pad1 [string repeat "  " [expr {$ind+1}]]
        switch -- $tag {
            str  { return "\"[esc $val]\"" }
            num  { return $val }
            bool { return [expr {$val ? "true" : "false"}] }
            null { return "null" }
            arr {
                if {[llength $val] == 0} { return "\[\]" }
                set p {}
                foreach it $val { lappend p "$pad1[dump $it [expr {$ind+1}]]" }
                return "\[\n[join $p ",\n"]\n$pad\]"
            }
            obj {
                if {[llength $val] == 0} { return "\{\}" }
                set p {}
                foreach {k v} $val { lappend p "$pad1\"[esc $k]\": [dump $v [expr {$ind+1}]]" }
                return "\{\n[join $p ",\n"]\n$pad\}"
            }
            default { return "\"[esc $node]\"" }
        }
    }
}
# Helper: turn a Tcl "counter array slice" into a J::obj, sorted by key
proc counts_to_obj {arrName prefix keys} {
    upvar 1 $arrName A
    set kv {}
    foreach k $keys {
        set full "$prefix|$k"
        set v [expr {[info exists A($full)] ? $A($full) : 0}]
        lappend kv $k [J::num $v]
    }
    return [J::obj {*}$kv]
}

# ----------------------------------------------------------------------------
# 2. Open the checkpoint
# ----------------------------------------------------------------------------
note "opening checkpoint: $OPT(dcp)"
open_checkpoint $OPT(dcp)
set design    [current_design]
set part      [get_property PART $design]
set top       [get_property TOP  $design]
set family    ""
catch { set family [get_property FAMILY       [get_parts $part]] }
set arch ""
catch { set arch   [get_property ARCHITECTURE [get_parts $part]] }

set is_placed 0
set is_routed 0
if {[llength [get_cells -quiet -hierarchical -filter {IS_PRIMITIVE==1 && LOC!=""}]] > 0} { set is_placed 1 }
catch {
    if {[llength [get_nets -quiet -hierarchical -filter {ROUTE_STATUS==ROUTED}]] > 0} { set is_routed 1 }
}
set stage [expr {$is_routed ? "routed" : ($is_placed ? "placed" : "synth")}]
note "part=$part top=$top family=$family arch=$arch stage=$stage"

set SCOPE $OPT(scope)
proc under_scope {name} {
    global SCOPE
    if {$SCOPE eq ""} { return 1 }
    return [expr {$name eq $SCOPE || [string match "$SCOPE/*" $name]}]
}
proc rel_depth {name} {
    global SCOPE
    set rel $name
    if {$SCOPE ne ""} { set rel [string range $name [expr {[string length $SCOPE]+1}] end] }
    if {$rel eq ""} { return 0 }
    return [llength [split $rel /]]
}
set ROOT_KEY [expr {$SCOPE eq "" ? "." : $SCOPE}]

if {$SCOPE ne "" && [llength [get_cells -quiet $SCOPE]] == 0} {
    puts stderr "ERROR: scope cell '$SCOPE' not found in design."
    puts stderr "Top-level instances are:"
    foreach c [lsort [get_cells -quiet *]] { puts stderr "    $c   ([get_property REF_NAME [get_cells $c]])" }
    exit 3
}

# ----------------------------------------------------------------------------
# 3. Hierarchy tree
# ----------------------------------------------------------------------------
note "walking hierarchy"
set all_hier [get_cells -quiet -hierarchical -filter {IS_PRIMITIVE==0}]
array unset MOD
set mod_paths {}
foreach c $all_hier {
    set n [get_property NAME $c]
    if {![under_scope $n]}  continue
    if {$n eq $SCOPE}       continue   ;# scope root handled via ROOT_KEY
    set MOD($n) 1
    lappend mod_paths $n
}
set mod_paths [lsort $mod_paths]

# children index + ref names
array set REF {}
array set CHILDREN {}
foreach n $mod_paths {
    set REF($n) [get_property REF_NAME [get_cells $n]]
    if {$REF($n) eq ""} { catch { set REF($n) [get_property ORIG_REF_NAME [get_cells $n]] } }
    set parent [join [lrange [split $n /] 0 end-1] /]
    lappend CHILDREN($parent) $n
}

# "cut nodes" = the hierarchy level used as graph nodes for connectivity:
#   rel_depth in [1..conn_depth], and (rel_depth==conn_depth OR no hierarchical child)
array unset CUT
foreach n $mod_paths {
    set d [rel_depth $n]
    if {$d < 1 || $d > $OPT(conn_depth)} continue
    set has_child [expr {[info exists CHILDREN($n)] && [llength $CHILDREN($n)] > 0}]
    if {$d == $OPT(conn_depth) || !$has_child} { set CUT($n) 1 }
}
note "hierarchy: [llength $mod_paths] modules, [array size CUT] graph-cut nodes (conn_depth=$OPT(conn_depth))"

proc nearest_cut {cellpath} {
    global CUT
    set segs [split $cellpath /]
    for {set i [llength $segs]} {$i >= 1} {incr i -1} {
        set pfx [join [lrange $segs 0 [expr {$i-1}]] /]
        if {[info exists CUT($pfx)]} { return $pfx }
    }
    return ""
}

# ----------------------------------------------------------------------------
# 4. Resource utilisation + placement footprint  (single pass over primitives)
# ----------------------------------------------------------------------------
note "classifying primitives"
set RES_TYPES {lut lut_logic lut_srl lut_dram ff carry muxf dsp bram36 bram18 uram other}

proc classify_ref {ref} {
    # returns list of {type weight} contributions
    switch -regexp -- $ref {
        {^LUT[1-6]$}                 { return {{lut 1} {lut_logic 1}} }
        {^SRL(16E|C16E|C32E)$}       { return {{lut 1} {lut_srl 1}} }
        {^(RAM(32|64|128|256|512)|RAMD(32|64|128)|RAMS(32|64)|DRAM)}  { return {{lut 1} {lut_dram 1}} }
        {^(FD[CPRS]E?|FDRE|FDSE|FDCE|FDPE|LDCE|LDPE)$} { return {{ff 1}} }
        {^CARRY(4|8)$}               { return {{carry 1}} }
        {^MUXF[5-9]$}                { return {{muxf 1}} }
        {^DSP(48E[12]|58|58C)?$}     { return {{dsp 1}} }
        {^DSP}                       { return {{dsp 1}} }
        {^RAMB36}                    { return {{bram36 1}} }
        {^RAMB18}                    { return {{bram18 1}} }
        {^(URAM288|URAM288E5)$}      { return {{uram 1}} }
        default                      { return {{other 1}} }
    }
}

set prims [get_cells -quiet -hierarchical -filter {IS_PRIMITIVE==1}]
note "  [llength $prims] primitives; attributing to ancestors"

array unset U   ;# inclusive:  key "path|type"
array unset X   ;# exclusive:  key "path|type"

# placement accumulators (filled later, need LOC list)
array unset PBB ;# "path|xmin" etc
array unset PCR ;# "path|<clockregion>" -> count
array unset PSLR
array unset PCELLS

foreach c $prims {
    set n   [get_property NAME $c]
    if {![under_scope $n]} continue
    set ref [get_property REF_NAME $c]
    set contribs [classify_ref $ref]

    set segs   [split $n /]
    set anc    [lrange $segs 0 end-1]
    set parent [join $anc /]

    foreach cw $contribs {
        lassign $cw type w
        # inclusive: root + every ancestor module under scope
        set uk "$ROOT_KEY|$type"
        set U($uk) [expr {([info exists U($uk)] ? $U($uk) : 0) + $w}]
        set cur ""
        foreach s $anc {
            set cur [expr {$cur eq "" ? $s : "$cur/$s"}]
            if {$cur eq $ROOT_KEY} continue
            if {[info exists MOD($cur)]} {
                set k "$cur|$type"
                set U($k) [expr {([info exists U($k)] ? $U($k) : 0) + $w}]
            }
        }
        # exclusive: immediate parent only
        set xk "$parent|$type"
        set X($xk) [expr {([info exists X($xk)] ? $X($xk) : 0) + $w}]
    }
}
note "utilisation roll-up done"

# ---- placement footprint (bulk property fetch, minimal Vivado round-trips) ----
if {$is_placed} {
    note "extracting placement footprint"
    set placed [get_cells -quiet -hierarchical -filter {IS_PRIMITIVE==1 && LOC!=""}]
    set locs   [get_property LOC $placed]
    # clock region per *unique* site (bounded)
    array unset SITE_CR
    set uniq [lsort -unique $locs]
    if {[llength $uniq] <= $OPT(max_uniq_sites)} {
        foreach s $uniq {
            set cr ""
            catch { set cr [get_property CLOCK_REGION [get_sites -quiet $s]] }
            set SITE_CR($s) $cr
        }
    } else {
        note "  >$OPT(max_uniq_sites) unique sites: skipping clock-region histogram"
    }

    foreach c $placed loc $locs {
        if {![regexp {_X([0-9]+)Y([0-9]+)} $loc -> px py]} continue
        set n [get_property NAME $c]
        if {![under_scope $n]} continue
        set cr  [expr {[info exists SITE_CR($loc)] ? $SITE_CR($loc) : ""}]
        set slr ""
        catch { set slr [get_property SLR [get_sites -quiet $loc]] }

        set segs [split $n /]
        set anc  [lrange $segs 0 end-1]

        # helper to bump one owner key
        set owners [list $ROOT_KEY]
        set cur ""
        foreach s $anc {
            set cur [expr {$cur eq "" ? $s : "$cur/$s"}]
            if {$cur eq $ROOT_KEY} continue
            if {[info exists MOD($cur)]} { lappend owners $cur }
        }
        foreach o $owners {
            if {![info exists PBB($o|xmin)]} {
                set PBB($o|xmin) $px ; set PBB($o|xmax) $px
                set PBB($o|ymin) $py ; set PBB($o|ymax) $py
            } else {
                if {$px < $PBB($o|xmin)} { set PBB($o|xmin) $px }
                if {$px > $PBB($o|xmax)} { set PBB($o|xmax) $px }
                if {$py < $PBB($o|ymin)} { set PBB($o|ymin) $py }
                if {$py > $PBB($o|ymax)} { set PBB($o|ymax) $py }
            }
            set PCELLS($o) [expr {([info exists PCELLS($o)] ? $PCELLS($o) : 0) + 1}]
            if {$cr ne ""}  { set PCR($o|$cr)  [expr {([info exists PCR($o|$cr)] ? $PCR($o|$cr) : 0) + 1}] }
            if {$slr ne ""} { set PSLR($o|$slr) [expr {([info exists PSLR($o|$slr)] ? $PSLR($o|$slr) : 0) + 1}] }
        }
    }
    note "placement footprint done ([llength $placed] placed cells)"
}

# ----------------------------------------------------------------------------
# 5. Clocks + per-module clock-domain membership
# ----------------------------------------------------------------------------
note "analysing clocks"
set clocks [get_clocks -quiet]
set clock_json {}
array unset CLKFF   ;# key "path|clk" -> FF count
set clk_names {}

foreach clk $clocks {
    set cn      [get_property NAME $clk]
    lappend clk_names $cn
    set period  [get_property PERIOD $clk]
    set freq    [expr {$period > 0 ? 1000.0/$period : 0}]
    set isgen   [get_property IS_GENERATED $clk]
    set src     ""
    catch { set src [get_property SOURCE_PINS $clk] }
    set master  ""
    catch { set master [get_property MASTER_CLOCK $clk] }
    lappend clock_json [J::obj \
        name        [J::str $cn] \
        period_ns   [J::num $period] \
        freq_mhz    [J::num [format %.3f $freq]] \
        is_generated [J::bool $isgen] \
        source_pins [J::str $src] \
        master_clock [J::str $master]]

    # registers on this clock -> attribute to module ancestors
    set regs {}
    catch { set regs [all_registers -quiet -clock $clk] }
    foreach r $regs {
        set n [get_property NAME $r]
        if {![under_scope $n]} continue
        set segs [split $n /]
        set anc  [lrange $segs 0 end-1]
        set k "$ROOT_KEY|$cn"
        set CLKFF($k) [expr {([info exists CLKFF($k)] ? $CLKFF($k) : 0) + 1}]
        set cur ""
        foreach s $anc {
            set cur [expr {$cur eq "" ? $s : "$cur/$s"}]
            if {$cur eq $ROOT_KEY} continue
            if {[info exists MOD($cur)]} {
                set k "$cur|$cn"
                set CLKFF($k) [expr {([info exists CLKFF($k)] ? $CLKFF($k) : 0) + 1}]
            }
        }
    }
}
note "clocks: [llength $clk_names] ([join $clk_names {, }])"

proc primary_clock {path} {
    global CLKFF clk_names
    set best "" ; set bestn -1
    foreach cn $clk_names {
        set k "$path|$cn"
        set v [expr {[info exists CLKFF($k)] ? $CLKFF($k) : 0}]
        if {$v > $bestn} { set bestn $v ; set best $cn }
    }
    return $best
}
proc module_clocks_obj {path} {
    global CLKFF clk_names
    set kv {}
    foreach cn $clk_names {
        set k "$path|$cn"
        if {[info exists CLKFF($k)] && $CLKFF($k) > 0} { lappend kv $cn [J::num $CLKFF($k)] }
    }
    return [J::obj {*}$kv]
}
proc is_multi_clock {path} {
    global CLKFF clk_names
    set c 0
    foreach cn $clk_names { if {[info exists CLKFF($path|$cn)] && $CLKFF($path|$cn) > 0} { incr c } }
    return [expr {$c > 1}]
}

# ----------------------------------------------------------------------------
# 6. Connectivity graph across the chosen hierarchy cut
# ----------------------------------------------------------------------------
note "tracing module-to-module connectivity"

proc base_of {pinname} {
    set leaf [lindex [split $pinname /] end]
    regsub {\[[0-9]+\]$} $leaf "" leaf
    return $leaf
}
proc protocol_of {base} {
    set b [string tolower $base]
    if {[regexp {t(valid|ready|data|last|keep|strb|user|dest|id)$} $b]} { return "axi_stream" }
    if {[regexp {(aw|ar)(addr|valid|ready|prot|len|size|burst|cache|lock|qos|region|id|user)$} $b]} { return "axi_mm" }
    if {[regexp {^(w|r|b)(data|valid|ready|resp|last|strb|id|user)$} $b]} { return "axi_mm" }
    return "generic"
}
# clock / reset / broadcast-enable nets: not "dataflow", they connect everything to everything
proc is_ctrl_name {s} {
    set b [string tolower [lindex [split $s /] end]]
    regsub {\[[0-9]+\]$} $b "" b
    # a clock/reset token at a name-boundary, optionally followed by _suffix tokens
    return [regexp {(^|_)([a-z]{0,2}clk|clock|clkin|clkout|reset|a?resetn|rstn?|srstn?|arstn?|por|power_on_reset)(_[a-z0-9]+)*$} $b]
}

array unset EB   ;# edge key -> bit count
array unset EN   ;# edge key -> representative net name
array unset EP   ;# edge key -> protocol
set edge_keys {}

# does get_nets support -boundary_type here?
set HAS_BT 1
if {[catch { get_nets -quiet -boundary_type upper -of [lindex [get_pins -quiet -of [get_cells [lindex [array names CUT] 0]]] 0] }]} {
    set HAS_BT 0
}

foreach m [lsort [array names CUT]] {
    set src_clk [primary_clock $m]
    foreach p [get_pins -quiet -of [get_cells $m]] {
        set dir  [get_property DIRECTION $p]
        if {$dir eq "IN" && !$OPT(include_glue)} {
            # inbound handled from the driver side; but still catch scope-port sources
        }
        if {$HAS_BT} {
            set net [get_nets -quiet -boundary_type upper -of $p]
        } else {
            set net [get_nets -quiet -of $p]
        }
        if {[llength $net] == 0} continue
        set net [lindex $net 0]
        set netname [get_property NAME $net]
        if {[regexp {(^|/)(GND|VCC)(/|$)} $netname]} continue

        set b [base_of [get_property NAME $p]]
        if {$OPT(drop_ctrl_nets) && ([is_ctrl_name $netname] || [is_ctrl_name $b])} continue

        set other_pins [get_pins -quiet -of $net]
        set other_ports [get_ports -quiet -of $net]

        # resolve endpoints -> cut modules (or scope port)
        set endpoints {}
        foreach op $other_pins {
            if {$op eq $p} continue
            set oc [get_cells -quiet -of $op]
            if {[llength $oc] == 0} continue
            set ocn [get_property NAME $oc]
            set cut [nearest_cut $ocn]
            if {$cut ne "" && $cut ne $m} {
                lappend endpoints [list mod $cut [base_of [get_property NAME $op]] [get_property DIRECTION $op]]
            }
        }
        foreach opt $other_ports {
            set pn [get_property NAME $opt]
            if {$OPT(collapse_ports)} { set pn [base_of $pn] }
            lappend endpoints [list port "PORT:$pn" $pn [get_property DIRECTION $opt]]
        }
        if {[llength $endpoints] == 0} continue

        foreach ep $endpoints {
            lassign $ep kind other obase odir
            # orient: prefer OUT -> IN
            if {$dir eq "OUT" || $odir eq "IN"} {
                set A $m ; set Ab $b ; set B $other ; set Bb $obase
            } elseif {$dir eq "IN" || $odir eq "OUT"} {
                set A $other ; set Ab $obase ; set B $m ; set Bb $b
            } else {
                # tie-break deterministically
                if {[string compare $m $other] <= 0} {
                    set A $m ; set Ab $b ; set B $other ; set Bb $obase
                } else {
                    set A $other ; set Ab $obase ; set B $m ; set Bb $b
                }
            }
            set key "$A\u0000$Ab\u0000$B\u0000$Bb"
            if {![info exists EB($key)]} {
                lappend edge_keys $key
                set EB($key) 0
                set EN($key) $netname
                set EP($key) [protocol_of $Ab]
            }
            incr EB($key)
        }
    }
}
note "connectivity: [llength $edge_keys] aggregated edges"

# ----------------------------------------------------------------------------
# 7. Registered-output ratio per cut module (pipeline-boundary signal)
# ----------------------------------------------------------------------------
note "measuring registered outputs per cut module"
array unset ROUT_TOT
array unset ROUT_REG
foreach m [lsort [array names CUT]] {
    set outpins [get_pins -quiet -of [get_cells $m] -filter {DIRECTION==OUT}]
    set tot 0 ; set reg 0
    foreach p $outpins {
        incr tot
        # driver leaf pin inside the module
        set net [expr {$HAS_BT ? [get_nets -quiet -boundary_type lower -of $p] : [get_nets -quiet -of $p]}]
        if {[llength $net] == 0} continue
        set drv [get_pins -quiet -leaf -of [lindex $net 0] -filter {DIRECTION==OUT}]
        if {[llength $drv] == 0} continue
        set dc  [get_cells -quiet -of [lindex $drv 0]]
        if {[llength $dc] == 0} continue
        if {[regexp {^(FD|LD)} [get_property REF_NAME $dc]]} { incr reg }
    }
    set ROUT_TOT($m) $tot
    set ROUT_REG($m) $reg
}

# ----------------------------------------------------------------------------
# 8. Pblocks / floorplan ranges
# ----------------------------------------------------------------------------
set pblock_json {}
foreach pb [get_pblocks -quiet] {
    set cells {}
    catch { set cells [get_cells -quiet -of [get_pblocks $pb]] }
    set clist {}
    foreach c [lrange $cells 0 199] { lappend clist [J::str [get_property NAME $c]] }
    lappend pblock_json [J::obj \
        name        [J::str $pb] \
        grid_ranges [J::str [get_property -quiet GRID_RANGES [get_pblocks $pb]]] \
        is_soft     [J::bool [get_property -quiet IS_SOFT [get_pblocks $pb]]] \
        cell_count  [J::num [llength $cells]] \
        cells       [J::arr $clist]]
}

# ----------------------------------------------------------------------------
# 9. Cross-check text reports (best-effort)
# ----------------------------------------------------------------------------
note "writing cross-check reports into $OPT(outdir)"
set aux {}
proc try_report {label cmd file} {
    global OPT aux
    set path [file join $OPT(outdir) $file]
    if {![catch { eval $cmd -file [list $path] } e]} {
        lappend aux $path
        note "  wrote $file"
    } else {
        note "  skipped $file ($e)"
    }
}
try_report util_hier  {report_utilization -hierarchical -hierarchical_depth 12} utilization_hier.rpt
try_report util_flat  {report_utilization}                                     utilization_flat.rpt
try_report clocks     {report_clocks}                                          clocks.rpt
try_report clk_net    {report_clock_networks}                                  clock_networks.rpt
try_report cdc        {report_cdc -details}                                    cdc.rpt
try_report dsgn_an    {report_design_analysis -logic_level_distribution -logic_level_dist_paths 1000} design_analysis.rpt
try_report timing     {report_timing_summary -delay_type max -max_paths 20}    timing_summary.rpt

# ----------------------------------------------------------------------------
# 10. Assemble JSON
# ----------------------------------------------------------------------------
note "assembling JSON"

# ---- modules ----
set modules_json {}
set emit_paths [concat [list $ROOT_KEY] $mod_paths]
foreach n $emit_paths {
    if {$n eq $ROOT_KEY} {
        set name  [expr {$SCOPE eq "" ? $top : [lindex [split $SCOPE /] end]}]
        set refnm [expr {$SCOPE eq "" ? $top : [get_property REF_NAME [get_cells $SCOPE]]}]
        set parent ""
        set depth 0
        set kids {}
        set base_for_children [expr {$SCOPE eq "" ? "" : $SCOPE}]
        if {[info exists CHILDREN($base_for_children)]} { set kids $CHILDREN($base_for_children) }
        set is_cut 0
    } else {
        set name  [lindex [split $n /] end]
        set refnm $REF($n)
        set parent [join [lrange [split $n /] 0 end-1] /]
        set depth [rel_depth $n]
        set kids  [expr {[info exists CHILDREN($n)] ? $CHILDREN($n) : {}}]
        set is_cut [info exists CUT($n)]
    }

    set kids_json {}
    foreach k [lsort $kids] { lappend kids_json [J::str $k] }

    set incl [counts_to_obj U $n $RES_TYPES]
    set excl [counts_to_obj X $n $RES_TYPES]
    # bram36-equivalent convenience
    set b36 [expr {[info exists U($n|bram36)] ? $U($n|bram36) : 0}]
    set b18 [expr {[info exists U($n|bram18)] ? $U($n|bram18) : 0}]

    set placement_json [J::null]
    if {$is_placed && [info exists PCELLS($n)]} {
        set crkv {}
        foreach key [lsort [array names PCR "$n|*"]] {
            set cr [lindex [split $key |] end]
            lappend crkv $cr [J::num $PCR($key)]
        }
        set slrkv {}
        foreach key [lsort [array names PSLR "$n|*"]] {
            set s [lindex [split $key |] end]
            lappend slrkv $s [J::num $PSLR($key)]
        }
        set placement_json [J::obj \
            slice_bbox [J::obj \
                xmin [J::num $PBB($n|xmin)] xmax [J::num $PBB($n|xmax)] \
                ymin [J::num $PBB($n|ymin)] ymax [J::num $PBB($n|ymax)] \
                width  [J::num [expr {$PBB($n|xmax)-$PBB($n|xmin)+1}]] \
                height [J::num [expr {$PBB($n|ymax)-$PBB($n|ymin)+1}]]] \
            placed_cells_counted [J::num $PCELLS($n)] \
            clock_region_histogram [J::obj {*}$crkv] \
            slr_histogram [J::obj {*}$slrkv]]
    }

    set rout_json [J::null]
    if {$is_cut && [info exists ROUT_TOT($n)] && $ROUT_TOT($n) > 0} {
        set rout_json [J::obj \
            out_pins       [J::num $ROUT_TOT($n)] \
            registered     [J::num $ROUT_REG($n)] \
            registered_ratio [J::num [format %.3f [expr {double($ROUT_REG($n))/$ROUT_TOT($n)}]]]]
    }

    lappend modules_json [J::obj \
        path            [J::str $n] \
        name            [J::str $name] \
        ref_name        [J::str $refnm] \
        parent          [J::str $parent] \
        rel_depth       [J::num $depth] \
        is_graph_node   [J::bool $is_cut] \
        children        [J::arr $kids_json] \
        util_inclusive  $incl \
        util_exclusive  $excl \
        bram36_equiv    [J::num [expr {$b36 + 0.5*$b18}]] \
        clock_ff_counts [module_clocks_obj $n] \
        primary_clock   [J::str [primary_clock $n]] \
        is_multi_clock  [J::bool [is_multi_clock $n]] \
        pipeline_boundary $rout_json \
        placement       $placement_json]
}

# ---- connectivity ----
set conn_json {}
foreach key $edge_keys {
    lassign [split $key "\u0000"] A Ab B Bb
    set aclk [primary_clock $A]
    set bclk [primary_clock $B]
    set cdc  [expr {$aclk ne "" && $bclk ne "" && $aclk ne $bclk}]
    lappend conn_json [J::obj \
        from        [J::str $A] \
        from_bus    [J::str $Ab] \
        to          [J::str $B] \
        to_bus      [J::str $Bb] \
        bits        [J::num $EB($key)] \
        protocol    [J::str $EP($key)] \
        sample_net  [J::str $EN($key)] \
        from_clock  [J::str $aclk] \
        to_clock    [J::str $bclk] \
        is_cdc      [J::bool $cdc]]
}

# ---- scope ports ----
set ports_json {}
array unset PORTW
foreach pt [get_ports -quiet] {
    set b [base_of [get_property NAME $pt]]
    set d [get_property DIRECTION $pt]
    set k "$b\u0000$d"
    set PORTW($k) [expr {([info exists PORTW($k)] ? $PORTW($k) : 0) + 1}]
}
foreach k [lsort [array names PORTW]] {
    lassign [split $k "\u0000"] b d
    lappend ports_json [J::obj bus [J::str $b] direction [J::str $d] bits [J::num $PORTW($k)]]
}

# ---- clocks list ----
# (clock_json already built)

# ---- pblocks (pblock_json already built) ----

# ---- meta / design ----
set host [info hostname]
set now  [clock format [clock seconds] -format "%Y-%m-%dT%H:%M:%S"]
set vv   [version -short]

set limitations {
    "Connectivity is a best-effort trace of sibling nets at the chosen hierarchy cut (conn_depth); pure combinational glue between modules at that level is collapsed, not modelled as its own node (set include_glue=1 to keep glue endpoints)."
    "By default (drop_ctrl_nets=1) nets whose name/pin base looks like a clock or reset are excluded from 'connectivity' so the graph shows dataflow, not the reset/clock fan-out mesh; set drop_ctrl_nets=0 to keep them. Top-level ports are collapsed bus-wise (collapse_ports=1)."
    "Bus width ('bits') counts distinct net bits seen crossing the boundary for that pin base name; it approximates AXI/stream channel width but multi-channel interfaces sharing a prefix may merge."
    "Pipeline depth is not reported as an absolute number. 'pipeline_boundary.registered_ratio' tells you whether a module's outputs are registered; per-stage latency needs timing-path sampling (see design_analysis.rpt logic-level distribution)."
    "'primary_clock' is the clock driving the most flip-flops in that module; modules with is_multi_clock=true straddle domains."
    "CDC flags on edges are derived from differing module primary clocks, not from report_cdc path analysis; consult cdc.rpt for the authoritative crossing list."
    "Placement bounding boxes are in SLICE column/row index space (not micrometres) and only cover placed leaf cells; routing detours are not included."
}
if {!$is_placed} { lappend limitations "Checkpoint is not placed: all 'placement' fields are null and SLR/clock-region data is unavailable." }
set lim_json {}
foreach l $limitations { lappend lim_json [J::str $l] }

set aux_json {}
foreach a $aux { lappend aux_json [J::str $a] }

set doc [J::obj \
    meta [J::obj \
        schema           [J::str "taoFPGA.architecture_data/1"] \
        script_version   [J::str $SCRIPT_VERSION] \
        generated        [J::str $now] \
        host             [J::str $host] \
        vivado_version   [J::str $vv] \
        checkpoint       [J::str [file normalize $OPT(dcp)]] \
        checkpoint_stage [J::str $stage] \
        scope            [J::str [expr {$SCOPE eq "" ? "(whole design)" : $SCOPE}]] \
        conn_depth       [J::num $OPT(conn_depth)] \
        aux_reports      [J::arr $aux_json] \
        limitations      [J::arr $lim_json]] \
    design [J::obj \
        top          [J::str $top] \
        part         [J::str $part] \
        family       [J::str $family] \
        architecture [J::str $arch] \
        is_placed    [J::bool $is_placed] \
        is_routed    [J::bool $is_routed] \
        totals       [counts_to_obj U $ROOT_KEY $RES_TYPES] \
        module_count [J::num [llength $mod_paths]] \
        graph_node_count [J::num [array size CUT]]] \
    clocks       [J::arr $clock_json] \
    ports        [J::arr $ports_json] \
    pblocks      [J::arr $pblock_json] \
    modules      [J::arr $modules_json] \
    connectivity [J::arr $conn_json]]

set fh [open $OPT(out) w]
puts $fh [J::dump $doc]
close $fh
note "wrote [file normalize $OPT(out)]  ([file size $OPT(out)] bytes)"

# ----------------------------------------------------------------------------
# 11. Bonus: Graphviz dataflow.dot
# ----------------------------------------------------------------------------
set dotpath [file join $OPT(outdir) dataflow.dot]
set dh [open $dotpath w]
puts $dh "digraph dataflow \{"
puts $dh "  rankdir=LR; splines=ortho; node \[shape=box style=\"rounded,filled\" fillcolor=\"#eef3fb\" fontname=Helvetica\];"
puts $dh "  edge \[fontname=Helvetica fontsize=9\];"
foreach m [lsort [array names CUT]] {
    set id [string map {/ __ . _ \[ _ \] _} $m]
    set lbl "$REF($m)\\n[lindex [split $m /] end]"
    set pc [primary_clock $m]
    if {$pc ne ""} { append lbl "\\n\[$pc\]" }
    puts $dh "  \"$id\" \[label=\"$lbl\"\];"
}
foreach key $edge_keys {
    lassign [split $key "\u0000"] A Ab B Bb
    if {![info exists CUT($A)] || ![info exists CUT($B)]} continue
    set ida [string map {/ __ . _ \[ _ \] _} $A]
    set idb [string map {/ __ . _ \[ _ \] _} $B]
    set w   [expr {1.0 + log([expr {$EB($key)+1}])}]
    set aclk [primary_clock $A] ; set bclk [primary_clock $B]
    set col [expr {($aclk ne "" && $bclk ne "" && $aclk ne $bclk) ? "\"#c0392b\"" : "\"#5b6b7f\""}]
    puts $dh "  \"$ida\" -> \"$idb\" \[label=\"$Ab ($EB($key))\" penwidth=[format %.2f $w] color=$col\];"
}
puts $dh "\}"
close $dh
note "wrote $dotpath"

note "DONE. JSON: $OPT(out)   reports: $OPT(outdir)/"
close_project
exit 0

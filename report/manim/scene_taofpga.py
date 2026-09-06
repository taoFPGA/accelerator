"""
taoFPGA: Hardware Accelerator for Vision Transformers
A 3Blue1Brown-style educational animation built with Manim Community Edition,
narrated with synchronized text-to-speech audio via manim-voiceover.

Render commands
----------------
Quick low-quality preview (fast, ~480p15), narration included:
    manim -pql scene_taofpga.py TaoFPGAOverview

Final high-quality render (1080p60), narration included:
    manim -pqh scene_taofpga.py TaoFPGAOverview

(-p opens the video when done; drop it for a headless render. -q[l|m|h|k]
selects quality: l=low/480p15, m=medium/720p30, h=high/1080p60, k=4k60.)

Individual scenes can also be rendered on their own -- each section is
broken out into its own Scene subclass below (Scene1Introduction,
Scene2SystolicArray, Scene3SoftmaxGelu, Scene4OutputLatency,
Scene5ViTDemo) in addition to the combined TaoFPGAOverview, e.g.:
    manim -pqh scene_taofpga.py Scene3SoftmaxGelu

Dependencies
------------
    pip install manim imageio-ffmpeg manim-voiceover "manim-voiceover[elevenlabs]" edge-tts
    A LaTeX distribution (MiKTeX on Windows, TeX Live on Linux/Mac) for
    the MathTex/Tex formulas -- manim shells out to latex to typeset them.

    Narration uses ElevenLabs (professional, documentary-style neural
    TTS) with the "Adam" voice. This requires an ElevenLabs API key:
    set the ELEVEN_API_KEY environment variable before rendering, e.g.
    (PowerShell):
        $env:ELEVEN_API_KEY = "<your key>"
    or (bash):
        export ELEVEN_API_KEY="<your key>"
    Audio is cached under media/voiceovers/ after first generation --
    subsequent renders of unchanged narration lines don't re-hit the
    API. A fallback EdgeTTSService (Microsoft Edge's free online TTS,
    "en-US-GuyNeural") is also defined below and requires no API key --
    swap it in via configure_narration() if ElevenLabs is unavailable.
"""
import asyncio
import os
from pathlib import Path

import edge_tts

from manim import (
    BOLD,
    DOWN,
    LEFT,
    ORIGIN,
    RIGHT,
    UP,
    AnimationGroup,
    Arrow,
    BarChart,
    Circle,
    Create,
    Dot,
    FadeIn,
    FadeOut,
    Flash,
    Group,
    ImageMobject,
    Indicate,
    Line,
    MathTex,
    MoveAlongPath,
    MovingCameraScene,
    RoundedRectangle,
    Succession,
    Text,
    TransformMatchingTex,
    VGroup,
    VMobject,
    ValueTracker,
    Wait,
    Write,
    linear,
    rate_functions,
)
from manim.mobject.text.numbers import DecimalNumber
from manim_voiceover import VoiceoverScene
from manim_voiceover.helper import remove_bookmarks
from manim_voiceover.services.base import SpeechService
from manim_voiceover.services.elevenlabs import ElevenLabsService


class EdgeTTSService(SpeechService):
    """A natural neural-voice TTS backend using Microsoft Edge's online
    service via the edge-tts library. Not bundled with manim-voiceover
    0.4.0 (only azure/gtts/elevenlabs/gemini/openai/pyttsx3 ship there),
    so implemented directly against its SpeechService interface --
    mirrors manim_voiceover.services.gtts.GTTSService, just swapping in
    edge_tts.Communicate for the actual synthesis call.
    """

    def __init__(self, voice: str = "en-US-GuyNeural", rate: str = "+0%", **kwargs):
        SpeechService.__init__(self, **kwargs)
        self.voice = voice
        self.rate = rate

    def generate_from_text(self, text, cache_dir=None, path=None, **kwargs):
        if cache_dir is None:
            cache_dir = self.cache_dir

        input_text = remove_bookmarks(text)
        input_data = {"input_text": input_text, "service": "edge_tts", "voice": self.voice}

        cached_result = self.get_cached_result(input_data, cache_dir)
        if cached_result is not None:
            return cached_result

        audio_path = (self.get_audio_basename(input_data) + ".mp3") if path is None else str(path)
        full_path = str(Path(cache_dir) / audio_path)

        async def _synthesize():
            communicate = edge_tts.Communicate(input_text, self.voice, rate=self.rate)
            await communicate.save(full_path)

        try:
            asyncio.run(_synthesize())
        except Exception as e:
            raise Exception(
                "edge-tts failed to generate narration audio -- this needs "
                "internet access to Microsoft's online TTS endpoint. If "
                "it's unreachable, switch configure_narration() below to "
                "GTTSService (manim_voiceover.services.gtts) or "
                "PyTTSX3Service (manim_voiceover.services.pyttsx3, fully "
                "offline via Windows SAPI)."
            ) from e

        return {
            "input_text": text,
            "input_data": input_data,
            "original_audio": audio_path,
        }


# Calm, clear, educational narrator voice (ElevenLabs' "Daniel - Steady
# Broadcaster"). "Josh" (TxGEqnHWrfWFTfGW9XjX) was the first choice but
# isn't in this account's voice library -- it was one of ElevenLabs'
# original 2022 premade voices, since retired from the default set for
# most accounts (confirmed by listing voices() and not finding it) --
# so Daniel was picked as the closest available steady, clear tone.
# Passed as a voice_id, not voice_name -- ElevenLabsService matches
# voice_name with an exact string equality check against the API's
# `name` field, which includes a style descriptor (e.g. "Daniel -
# Steady Broadcaster"), so the bare first name alone never matches and
# silently falls back to the library's first voice.
NARRATOR_VOICE_ID = "onwK4e9ZLuTAKqWW03F9"
NARRATOR_MODEL = "eleven_multilingual_v2"  # eleven_monolingual_v1 (the
# manim-voiceover default) was deprecated by ElevenLabs; this is their
# current flagship-quality TTS model.


# Calm, engaging, clear educational delivery (3Blue1Brown style, not a
# flat news-broadcast read): stability well above default keeps the
# performance steady rather than erratic, but a touch of style keeps
# it from sounding monotone -- some warmth/inflection is what makes an
# explainer feel "engaging" rather than just "calm." The unhurried
# pacing itself comes mostly from sentence structure (deliberate
# punctuation, see the narration text below) and from the self.wait()
# gaps placed between narration segments throughout each scene method,
# not from a synthesis-side speed knob -- manim-voiceover's
# global_speed does a pitch-preserving SoX tempo stretch, but the SoX
# build available via winget on Windows ships neither soxi.exe nor MP3
# codec support, so it can't actually run here.
NARRATOR_VOICE_SETTINGS = {
    "stability": 0.65,
    "similarity_boost": 0.8,
    "style": 0.15,
    "use_speaker_boost": True,
}


def configure_narration(scene):
    """Attach the TTS backend to a VoiceoverScene instance.

    Requires the ELEVEN_API_KEY environment variable to be set to a
    valid ElevenLabs API key. To use the no-API-key fallback instead,
    replace the line below with:
        scene.set_speech_service(EdgeTTSService(voice="en-US-GuyNeural", rate="-8%"))
    """
    scene.set_speech_service(
        ElevenLabsService(
            voice_id=NARRATOR_VOICE_ID,
            model=NARRATOR_MODEL,
            voice_settings=NARRATOR_VOICE_SETTINGS,
            # ElevenLabsService defaults to transcription_model="base",
            # which -- if the optional whisper/stable_whisper extras
            # aren't installed -- interactively prompts on stdin and
            # hangs a non-interactive render. We don't need word-level
            # transcription (no bookmark-synced captions in this script).
            transcription_model=None,
        )
    )

# --------------------------------------------------------------------------
# 3Blue1Brown-inspired palette
# --------------------------------------------------------------------------
BG_COLOR = "#1C1C1E"
BLUE_ACCENT = "#58C4DD"
TEAL_ACCENT = "#83C5BE"
GOLD_ACCENT = "#F4D06F"
RED_ACCENT = "#E76F51"
WHITE_TEXT = "#FFFFFF"
DIM_TEXT = "#A0A0A5"

HERE = os.path.dirname(os.path.abspath(__file__))
DOG_IMAGE_PATH = os.path.join(HERE, "..", "..", "apps", "vit", "assets", "sample_dog.jpg")


def make_block(label, color, width=3.2, height=1.5, font_size=20):
    """A rounded, softly-filled block with a centered label -- the shared
    visual language for every pipeline-stage box across all five scenes."""
    rect = RoundedRectangle(
        corner_radius=0.18, width=width, height=height,
        color=color, fill_color=color, fill_opacity=0.12, stroke_width=3,
    )
    text = Text(label, font_size=font_size, color=WHITE_TEXT, line_spacing=1.1)
    if text.width > width - 0.3:
        text.scale_to_fit_width(width - 0.3)
    text.move_to(rect.get_center())
    return VGroup(rect, text)


def make_flag_light(label, color):
    """A small labelled indicator circle -- used for the Softmax pass
    flags (length1_flag / length2_flag / length3_flag) and for
    out_valid / out_last in the output-streaming scene."""
    dot = Circle(radius=0.16, color=color, fill_color=color, fill_opacity=0.15, stroke_width=3)
    text = Text(label, font_size=16, color=DIM_TEXT)
    text.next_to(dot, DOWN, buff=0.12)
    return VGroup(dot, text)


def light_on(flag_group, color):
    dot = flag_group[0]
    return dot.animate.set_fill(color, opacity=0.95)


def light_off(flag_group):
    dot = flag_group[0]
    return dot.animate.set_fill(dot.get_color(), opacity=0.15)


class TaoFPGAOverview(VoiceoverScene, MovingCameraScene):
    """The complete five-part video, run end to end, with narration."""

    def construct(self):
        configure_narration(self)
        self.camera.background_color = BG_COLOR
        self.scene_1_introduction()
        self.scene_2_systolic_array()
        self.scene_3_softmax_gelu()
        self.scene_4_output_latency()
        self.scene_5_vit_demo()

    # ----------------------------------------------------------------
    # Scene 1 -- Introduction & High-Level Block Architecture
    # ----------------------------------------------------------------
    def scene_1_introduction(self):
        title = Text(
            "taoFPGA: Hardware Accelerator for Vision Transformers",
            font_size=34, color=WHITE_TEXT, weight=BOLD,
        ).to_edge(UP, buff=0.6)
        subtitle = Text(
            "A quantized INT8 transformer processing core on a Xilinx Zynq-7020",
            font_size=20, color=DIM_TEXT,
        ).next_to(title, DOWN, buff=0.25)

        with self.voiceover(
            text="taoFPGA is a hardware accelerator for Vision Transformers. "
                 "It's a quantized, INT8 transformer processing core... "
                 "built on a Xilinx Zynq-7020 system on chip."
        ):
            self.play(Write(title), run_time=1.2)
            self.play(FadeIn(subtitle, shift=UP * 0.2), run_time=0.8)
        self.wait(0.35)

        b1 = make_block("AXI-Stream Input\n2x 128-bit: Feature & Weight", TEAL_ACCENT)
        b2 = make_block("Systolic Array\n16x16 PE Grid (MACs)", BLUE_ACCENT)
        b3 = make_block("Softmax + GELU\nEngines", GOLD_ACCENT)
        b4 = make_block("AXI-Stream Output\n32-bit valid/ready/last", RED_ACCENT)

        blocks = VGroup(b1, b2, b3, b4).arrange(RIGHT, buff=0.9)
        if blocks.width > 12.5:
            blocks.scale_to_fit_width(12.5)
        blocks.move_to(ORIGIN).shift(DOWN * 0.4)

        arrows = VGroup(*[
            Arrow(blocks[i].get_right(), blocks[i + 1].get_left(),
                  buff=0.08, color=WHITE_TEXT, stroke_width=3, max_tip_length_to_length_ratio=0.15)
            for i in range(len(blocks) - 1)
        ])

        with self.voiceover(
            text="Data enters through two separate 128-bit AXI-Stream "
                 "interfaces... one for feature tokens, one for weights."
        ):
            self.play(Create(b1[0]), FadeIn(b1[1]), run_time=0.5)
        self.wait(0.3)

        with self.voiceover(
            text="It flows into a systolic array of processing elements "
                 "that perform the core matrix multiplications."
        ):
            self.play(Create(b2[0]), FadeIn(b2[1]), run_time=0.5)
            self.play(Create(arrows[0]))
        self.wait(0.3)

        with self.voiceover(
            text="From there, it passes through dedicated Softmax and "
                 "GELU engines for the non-linear operations."
        ):
            self.play(Create(b3[0]), FadeIn(b3[1]), run_time=0.5)
            self.play(Create(arrows[1]))
        self.wait(0.3)

        with self.voiceover(
            text="And finally... it streams out through a 32-bit "
                 "AXI-Stream interface."
        ):
            self.play(Create(b4[0]), FadeIn(b4[1]), run_time=0.5)
            self.play(Create(arrows[2]))

            # A data token travelling end to end previews the pipeline flow.
            token = Dot(color=GOLD_ACCENT, radius=0.11).move_to(blocks[0].get_left() + LEFT * 0.4)
            waypoints = [token.get_center()] + [b.get_center() for b in blocks] + [blocks[-1].get_right() + RIGHT * 0.4]
            path = VMobject().set_points_as_corners(waypoints)

            self.play(FadeIn(token))
            self.play(MoveAlongPath(token, path), run_time=2.4, rate_func=linear)
        self.wait(0.35)

        self.play(FadeOut(VGroup(title, subtitle, blocks, arrows, token)))
        self.wait(0.3)

    # ----------------------------------------------------------------
    # Scene 2 -- Systolic Array Dataflow
    # ----------------------------------------------------------------
    def scene_2_systolic_array(self):
        title = Text("Systolic Array: Weight-Stationary Matrix Multiplication",
                      font_size=30, color=WHITE_TEXT, weight=BOLD).to_edge(UP, buff=0.6)
        self.play(Write(title), run_time=1.0)

        n = 4  # a 4x4 illustrative grid stands in for the real 16x16 array
        cell_size = 0.9
        grid = VGroup()
        cells = [[None] * n for _ in range(n)]
        for r in range(n):
            for c in range(n):
                cell = RoundedRectangle(
                    corner_radius=0.08, width=cell_size, height=cell_size,
                    color=BLUE_ACCENT, fill_color=BLUE_ACCENT, fill_opacity=0.10, stroke_width=2.5,
                )
                cell.move_to(RIGHT * c * cell_size + DOWN * r * cell_size)
                cells[r][c] = cell
                grid.add(cell)
        grid.move_to(ORIGIN).shift(DOWN * 0.2)
        pe_label = Text("PE = INT8 multiply-accumulate", font_size=18, color=DIM_TEXT)
        pe_label.next_to(grid, DOWN, buff=0.5)

        self.play(Create(grid), run_time=1.2)
        self.play(FadeIn(pe_label))
        self.wait(0.4)

        # Weight tokens loaded into each column from the top (stationary).
        weight_dots = VGroup()
        weight_anims = []
        for c in range(n):
            w = RoundedRectangle(width=cell_size * 0.5, height=cell_size * 0.3,
                                  corner_radius=0.04, color=GOLD_ACCENT,
                                  fill_color=GOLD_ACCENT, fill_opacity=0.9, stroke_width=1)
            start = cells[0][c].get_top() + UP * 1.0
            w.move_to(start)
            weight_dots.add(w)
            weight_anims.append(FadeIn(w))
        weight_caption = Text("weights loaded, held stationary", font_size=16, color=GOLD_ACCENT)
        weight_caption.next_to(grid, UP, buff=0.3)

        with self.voiceover(
            text="The systolic array is weight-stationary."
        ):
            self.play(AnimationGroup(*weight_anims, lag_ratio=0.15), run_time=0.8)
        self.wait(0.3)

        with self.voiceover(
            text="Each processing element loads its weight once... and "
                 "holds it fixed."
        ):
            self.play(AnimationGroup(*[
                weight_dots[c].animate.move_to(cells[0][c].get_center())
                for c in range(n)
            ], lag_ratio=0.1), run_time=1.0)
            self.play(FadeIn(weight_caption))
        self.wait(0.35)

        # Feature tokens stream in from the left, row by row.
        feature_dots = VGroup()
        feature_anims = []
        for r in range(n):
            f = Dot(radius=0.14, color=TEAL_ACCENT, fill_opacity=0.9)
            start = cells[r][0].get_left() + LEFT * 1.2
            f.move_to(start)
            feature_dots.add(f)
            feature_anims.append(FadeIn(f))

        # Diagonal systolic wavefront: cells on the same anti-diagonal
        # (row + col constant) receive data -- and therefore compute --
        # simultaneously, one clock tick apart between diagonals.
        diagonals = {}
        for r in range(n):
            for c in range(n):
                diagonals.setdefault(r + c, []).append(cells[r][c])

        feature_move = AnimationGroup(*[
            feature_dots[r].animate.move_to(cells[r][n - 1].get_center() + RIGHT * cell_size * 0.5)
            for r in range(n)
        ], run_time=(2 * n - 1) * 0.35)

        flash_steps = []
        for d in sorted(diagonals):
            group = diagonals[d]
            flash_steps.append(AnimationGroup(*[
                Indicate(cell, color=GOLD_ACCENT, scale_factor=1.12) for cell in group
            ], run_time=0.3))
        wavefront = Succession(*flash_steps, lag_ratio=1.0)

        mac_caption = Text("MAC wavefront: psum = psum_in + x_in x reg_w, one diagonal per clock",
                            font_size=16, color=DIM_TEXT)
        mac_caption.next_to(pe_label, DOWN, buff=0.25)

        with self.voiceover(
            text="Now, feature tokens stream in from the left, one row at a "
                 "time."
        ):
            self.play(AnimationGroup(*feature_anims, lag_ratio=0.15), run_time=0.6)
            self.play(FadeIn(mac_caption))
        self.wait(0.3)

        with self.voiceover(
            text="Multiply-accumulate operations ripple across the array in "
                 "a diagonal wavefront... one clock cycle per diagonal... "
                 "until every partial sum has been computed."
        ):
            self.play(feature_move, wavefront)
        self.wait(0.35)

        self.play(FadeOut(VGroup(title, grid, pe_label, weight_dots, weight_caption,
                                  feature_dots, mac_caption)))
        self.wait(0.3)

    # ----------------------------------------------------------------
    # Scene 3 -- Dedicated 3-Pass Softmax & Non-Linear Pipeline
    # ----------------------------------------------------------------
    def scene_3_softmax_gelu(self):
        title = Text("Dedicated 3-Pass Softmax & GELU Pipeline",
                      font_size=30, color=WHITE_TEXT, weight=BOLD).to_edge(UP, buff=0.6)
        self.play(Write(title), run_time=1.0)

        why = Text(
            "Why hardware Softmax is tricky: numerical stability (max-subtraction)\n"
            "and division-free normalization, all with a bounded pipeline.",
            font_size=18, color=DIM_TEXT, line_spacing=1.2,
        ).next_to(title, DOWN, buff=0.3)
        with self.voiceover(
            text="Softmax in hardware is deceptively hard: it needs "
                 "numerical stability and a division, both expensive in "
                 "fixed-point logic."
        ):
            self.play(FadeIn(why))
        self.wait(0.3)
        with self.voiceover(
            text="taoFPGA solves this with a dedicated three-pass pipeline."
        ):
            pass
        self.wait(0.35)

        # A small row of tokens (x_i) that the three passes sweep over.
        n_tokens = 6
        tokens = VGroup(*[
            RoundedRectangle(width=0.9, height=0.7, corner_radius=0.08,
                              color=BLUE_ACCENT, fill_color=BLUE_ACCENT,
                              fill_opacity=0.12, stroke_width=2.5)
            for _ in range(n_tokens)
        ]).arrange(RIGHT, buff=0.25)
        token_labels = VGroup(*[
            MathTex(f"x_{{{i}}}", font_size=26, color=WHITE_TEXT).move_to(tokens[i].get_center())
            for i in range(n_tokens)
        ])
        row = VGroup(tokens, token_labels)
        row.to_edge(UP, buff=1.4)

        self.play(FadeOut(why), Create(tokens), FadeIn(token_labels), run_time=1.0)

        flag1 = make_flag_light("length1_flag", GOLD_ACCENT).next_to(row, DOWN, buff=0.7).shift(LEFT * 3.5)
        flag2 = make_flag_light("length2_flag", GOLD_ACCENT).next_to(flag1, RIGHT, buff=1.2)
        flag3 = make_flag_light("length3_flag", GOLD_ACCENT).next_to(flag2, RIGHT, buff=1.2)
        self.play(FadeIn(flag1), FadeIn(flag2), FadeIn(flag3))

        scanner = RoundedRectangle(width=0.95, height=0.75, corner_radius=0.1,
                                    color=GOLD_ACCENT, stroke_width=4, fill_opacity=0)
        scanner.move_to(tokens[0].get_center())

        def sweep(run_time=1.4):
            return scanner.animate(run_time=run_time, rate_func=linear).move_to(tokens[-1].get_center())

        flags_row = VGroup(flag1, flag2, flag3)

        # Pass 1: MAX
        with self.voiceover(
            text="In the first pass, the engine scans every token to find "
                 "the maximum value... guarding against overflow in the "
                 "exponent that follows."
        ):
            self.play(light_on(flag1, GOLD_ACCENT), FadeIn(scanner))
            formula1 = MathTex(r"m = \max_i(x_i)", font_size=34, color=GOLD_ACCENT)
            formula1.scale(0.85)
            formula1.next_to(flags_row, DOWN, buff=0.6)
            self.play(Write(formula1))
            scanner.move_to(tokens[0].get_center())
            self.play(sweep())
            self.play(light_off(flag1))
        self.wait(0.35)

        # Pass 2: ACCUMULATE
        with self.voiceover(
            text="In the second pass, it exponentiates each value shifted by "
                 "that maximum, and accumulates the results into a running "
                 "sum."
        ):
            self.play(light_on(flag2, GOLD_ACCENT))
            formula2 = MathTex(r"S = \sum_i e^{x_i - m}", font_size=34, color=GOLD_ACCENT)
            formula2.scale(0.85)
            formula2.move_to(formula1)
            self.play(TransformMatchingTex(formula1, formula2))
            scanner.move_to(tokens[0].get_center())
            self.play(sweep())
            self.play(light_off(flag2))
        self.wait(0.35)

        # Pass 3: NORMALIZE
        with self.voiceover(
            text="In the third and final pass, each exponentiated value is "
                 "normalized by that sum, producing the attention weights."
        ):
            self.play(light_on(flag3, GOLD_ACCENT))
            formula3 = MathTex(r"y_i = \frac{e^{x_i - m}}{S}", font_size=34, color=GOLD_ACCENT)
            formula3.scale(0.85)
            formula3.move_to(formula2)
            self.play(TransformMatchingTex(formula2, formula3))
            scanner.move_to(tokens[0].get_center())
            self.play(sweep())
            self.play(light_off(flag3), FadeOut(scanner))
        self.wait(0.35)

        # Flow normalized weights into GELU -- anchored to the bottom edge
        # (rather than placed relative to formula3) so it never clips off
        # screen regardless of how tall the formula stack above it is.
        # Widened to fit the RTL's actual tanh-based approximation (see
        # sourcecode/core/gelu.v, validated against this exact formula in
        # tb/gelu_tb.sv) -- NOT the exact erf-based GELU(x) = x*Phi(x),
        # which is only what the separate software ViT reference model
        # (apps/vit/vit_numpy.py) uses, not what's on this chip.
        gelu_block = make_block("GELU\nActivation", RED_ACCENT, width=9.0, height=1.3)
        gelu_block.scale(0.85)
        gelu_block.to_edge(DOWN, buff=0.6)
        gelu_formula = MathTex(
            r"\text{GELU}(x) \approx 0.5x\left(1+\tanh\left["
            r"\sqrt{\tfrac{2}{\pi}}\,(x+0.044715x^3)\right]\right)",
            font_size=26, color=WHITE_TEXT,
        )
        gelu_formula.move_to(gelu_block.get_center())
        gelu_formula.scale_to_fit_width(gelu_block.width - 0.3)

        arrow_to_gelu = Arrow(formula3.get_bottom(), gelu_block.get_top(),
                               buff=0.15, color=WHITE_TEXT, stroke_width=3)
        with self.voiceover(
            text="The normalized attention weights then flow into a "
                 "dedicated GELU activation unit before continuing through "
                 "the pipeline."
        ):
            self.play(Create(gelu_block[0]), Create(arrow_to_gelu))
            self.play(Write(gelu_formula))
        self.wait(0.35)

        self.play(FadeOut(VGroup(
            title, row, flag1, flag2, flag3, formula3, gelu_block, gelu_formula, arrow_to_gelu,
        )))
        self.wait(0.3)

    # ----------------------------------------------------------------
    # Scene 4 -- Output Streaming & Latency Sign-Off
    # ----------------------------------------------------------------
    def scene_4_output_latency(self):
        title = Text("Output Streaming & Latency Sign-Off",
                      font_size=30, color=WHITE_TEXT, weight=BOLD).to_edge(UP, buff=0.6)
        self.play(Write(title), run_time=1.0)

        bus_line = Line(LEFT * 5, RIGHT * 5, color=DIM_TEXT, stroke_width=2)
        bus_line.move_to(ORIGIN).shift(UP * 0.6)
        bus_label = Text("AXI-Stream Output (32-bit)", font_size=18, color=DIM_TEXT)
        bus_label.next_to(bus_line, UP, buff=0.2)
        self.play(Create(bus_line), FadeIn(bus_label))

        valid_flag = make_flag_light("out_valid", TEAL_ACCENT).next_to(bus_line, DOWN, buff=0.8).shift(LEFT * 3.5)
        last_flag = make_flag_light("out_last", RED_ACCENT).next_to(valid_flag, RIGHT, buff=1.5)

        # Stream of output tokens with out_valid pulsing alongside.
        n_out = 6
        out_tokens = VGroup(*[
            RoundedRectangle(width=0.5, height=0.5, corner_radius=0.06,
                              color=TEAL_ACCENT, fill_color=TEAL_ACCENT, fill_opacity=0.85, stroke_width=1)
            for _ in range(n_out)
        ])
        for i, tok in enumerate(out_tokens):
            tok.move_to(bus_line.get_start() + RIGHT * (0.8 * i))

        move_anims = []
        for i, tok in enumerate(out_tokens):
            move_anims.append(tok.animate(run_time=2.2, rate_func=linear).move_to(bus_line.get_end() + LEFT * 0.3))

        with self.voiceover(
            text="On the output side, results stream out over a 32-bit "
                 "AXI-Stream bus, with a valid signal pulsing for every word, "
                 "and a single-cycle last signal marking the end of each "
                 "packet."
        ):
            self.play(FadeIn(valid_flag), FadeIn(last_flag))
            self.play(FadeIn(out_tokens, lag_ratio=0.15))
            self.play(
                AnimationGroup(*move_anims),
                Succession(*[
                    AnimationGroup(light_on(valid_flag, TEAL_ACCENT), Wait(0.15), light_off(valid_flag))
                    for _ in range(n_out)
                ], lag_ratio=1.0),
            )

            # out_last: a single-cycle pulse at packet completion.
            self.play(Flash(last_flag[0], color=RED_ACCENT, flash_radius=0.45, line_length=0.25))
            self.play(light_on(last_flag, RED_ACCENT))
            self.wait(0.2)
            self.play(light_off(last_flag))
        self.wait(0.35)

        # Cycle counter locking at the real, measured latency.
        counter_label = Text("Hardware Cycle Counter", font_size=18, color=DIM_TEXT)
        counter = DecimalNumber(0, num_decimal_places=0, color=GOLD_ACCENT).scale(1.6)
        counter_group = VGroup(counter_label, counter).arrange(DOWN, buff=0.25)
        counter_group.next_to(VGroup(valid_flag, last_flag), DOWN, buff=0.9)

        result_text = Text("Total Hardware Latency: 18,083 Cycles",
                            font_size=26, color=WHITE_TEXT, weight=BOLD)
        result_text.next_to(counter_group, DOWN, buff=0.4)

        with self.voiceover(
            text="Across the full pipeline, hardware simulation converges on "
                 "a fixed, deterministic latency: eighteen thousand and "
                 "eighty-three clock cycles, measured directly from Cadence "
                 "Xcelium simulation."
        ):
            self.play(FadeIn(counter_group))
            tracker = ValueTracker(0)
            counter.add_updater(lambda m: m.set_value(tracker.get_value()))
            self.play(tracker.animate.set_value(18083), run_time=1.8, rate_func=rate_functions.ease_out_expo)
            counter.clear_updaters()
            counter.set_value(18083)
            self.play(Write(result_text))
        self.wait(0.35)

        self.play(FadeOut(VGroup(
            title, bus_line, bus_label, valid_flag, last_flag, out_tokens,
            counter_group, result_text,
        )))
        self.wait(0.3)

    # ----------------------------------------------------------------
    # Scene 5 -- Software Correctness Check: ViT-Tiny Reference Model
    #
    # IMPORTANT SCOPE NOTE: this scene demonstrates the pure-software
    # (NumPy) ViT-Tiny reference model classifying a real dog photo --
    # it validates that reference implementation against PyTorch, and
    # is entirely separate from the taoFPGA hardware kernel benchmark
    # in Scene 4. Per report/project_story.md section 30, the real
    # accelerator has no ViT sub-block it can be substituted into and
    # still produce numerically correct results, so this classification
    # never runs "through the accelerated pipeline" -- it runs on the
    # ARM/dev-machine CPU. Do not word this scene's narration or
    # labels as if the FPGA did this inference.
    # ----------------------------------------------------------------
    def scene_5_vit_demo(self):
        title = Text("Software Correctness Check: ViT-Tiny Reference Model",
                      font_size=28, color=WHITE_TEXT, weight=BOLD).to_edge(UP, buff=0.6)
        self.play(Write(title), run_time=1.0)

        # Real test image if available, with a graceful built-in-shape
        # fallback otherwise (per the brief's own requirement) -- this
        # is the actual photo the project's own ViT-Tiny validation
        # classified as "Samoyed, 87.26% confidence" (see
        # apps/vit/export_vit_weights.py / project_story.md).
        try:
            if not os.path.isfile(DOG_IMAGE_PATH):
                raise FileNotFoundError(DOG_IMAGE_PATH)
            image = ImageMobject(DOG_IMAGE_PATH)
            image.scale_to_fit_height(3.2)
        except Exception:
            image = RoundedRectangle(width=3.2, height=3.2, corner_radius=0.1,
                                      color=DIM_TEXT, fill_color=DIM_TEXT, fill_opacity=0.25)
            placeholder_label = Text("input image\n(placeholder)", font_size=16, color=WHITE_TEXT)
            placeholder_label.move_to(image.get_center())
            image = VGroup(image, placeholder_label)
        image.move_to(LEFT * 4.2 + DOWN * 0.3)

        with self.voiceover(
            text="Separately, to validate correctness... a full ViT-Tiny "
                 "model was run in software, on a real photograph of a dog."
        ):
            self.play(FadeIn(image))
        self.wait(0.35)

        # Patch-embedding grid overlay.
        img_w = image.width if hasattr(image, "width") else 3.2
        img_h = image.height if hasattr(image, "height") else 3.2
        patch_grid = VGroup()
        n_patches = 4
        for i in range(1, n_patches):
            x = image.get_left()[0] + img_w * i / n_patches
            patch_grid.add(Line([x, image.get_top()[1], 0], [x, image.get_bottom()[1], 0],
                                 color=WHITE_TEXT, stroke_width=1, stroke_opacity=0.6))
            y = image.get_bottom()[1] + img_h * i / n_patches
            patch_grid.add(Line([image.get_left()[0], y, 0], [image.get_right()[0], y, 0],
                                 color=WHITE_TEXT, stroke_width=1, stroke_opacity=0.6))
        patch_caption = Text("patchify (16x16 patches)", font_size=16, color=DIM_TEXT)
        patch_caption.next_to(image, DOWN, buff=0.3)

        # A neutral (non-hardware-colored) block for the software
        # reference model, deliberately distinct from Scene 1-4's
        # BLUE_ACCENT/TEAL_ACCENT hardware blocks -- this is NumPy on a
        # CPU, not the FPGA.
        tblock = make_block("ViT-Tiny\n(NumPy Reference)", DIM_TEXT, width=2.8, height=1.6)
        tblock.move_to(ORIGIN).shift(DOWN * 0.3)
        arrow_in = Arrow(image.get_right(), tblock.get_left(), buff=0.15, color=WHITE_TEXT, stroke_width=3)

        # A handful of patch tokens streaming into the block.
        patch_tokens = VGroup(*[Dot(radius=0.08, color=GOLD_ACCENT) for _ in range(5)])
        for i, tok in enumerate(patch_tokens):
            tok.move_to(image.get_right() + RIGHT * 0.1 + UP * (0.5 - i * 0.25))

        with self.voiceover(
            text="The image is patchified into sixteen-by-sixteen tiles..."
        ):
            self.play(Create(patch_grid), run_time=1.0)
            self.play(FadeIn(patch_caption))
        self.wait(0.3)

        with self.voiceover(
            text="...and embedded into tokens that flow through the "
                 "twelve-layer ViT-Tiny network -- the same model whose "
                 "matmul, softmax, and GELU shapes were used for the "
                 "hardware kernel benchmark."
        ):
            self.play(Create(tblock[0]), FadeIn(tblock[1]))
            self.play(Create(arrow_in))
            self.play(FadeIn(patch_tokens, lag_ratio=0.1))
            self.play(AnimationGroup(*[
                tok.animate.move_to(tblock.get_center()) for tok in patch_tokens
            ], lag_ratio=0.08), run_time=1.2)
            self.play(FadeOut(patch_tokens))
        self.wait(0.35)

        # Output classification bars -- exact measured Top-5 output from
        # the ViT-Tiny reference run (see apps/vit/export_vit_weights.py /
        # project_story.md): Samoyed at 87.26% confidence, well clear of
        # the next four closest breeds.
        top5_labels = ["Samoyed", "Pomeranian", "Arctic fox", "Keeshond", "Eskimo dog"]
        top5_values = [87.26, 6.80, 1.01, 1.00, 0.53]
        chart = BarChart(
            values=top5_values,
            bar_names=top5_labels,
            y_range=[0, 100, 25],
            y_length=3.0,
            x_length=6.2,
            bar_colors=[GOLD_ACCENT, DIM_TEXT, DIM_TEXT, DIM_TEXT, DIM_TEXT],
        )
        # Built extra wide (x_length=6.2) so five bar-name labels -- two
        # of them two words long -- get real breathing room, then scaled
        # down as a whole: this shrinks the (fixed-size) label text along
        # with everything else, so the final footprint clears the
        # transformer block's right edge (x=1.3) with room for the
        # y-axis tick labels (which extend further left than the axis
        # line itself) while the bar names no longer touch each other.
        chart.scale(0.68)
        chart.move_to(RIGHT * 4.4 + DOWN * 0.2)
        arrow_out = Arrow(tblock.get_right(), chart.get_left(), buff=0.15, color=WHITE_TEXT, stroke_width=3)

        # Centered on the full frame (not on the chart's off-center x
        # position) so a long line never clips off the right edge.
        result_text = Text('Predicted Class: Samoyed (87.26% Top-1 Confidence)',
                            font_size=22, color=GOLD_ACCENT, weight=BOLD)
        result_text.move_to(DOWN * 2.6)
        top5_caption = Text("Top-5 classification validates run against known-correct reference",
                             font_size=16, color=DIM_TEXT)
        top5_caption.next_to(result_text, DOWN, buff=0.2)

        with self.voiceover(
            text="The resulting top-five classification confirms a correct, "
                 "high-confidence prediction: Samoyed, at eighty-seven point "
                 "two six percent, well ahead of the next closest breed."
        ):
            self.play(Create(arrow_out))
            self.play(Create(chart), run_time=1.2)
            self.play(Indicate(chart.bars[0], color=GOLD_ACCENT, scale_factor=1.08))
            self.play(Write(result_text))
            self.play(FadeIn(top5_caption))
        self.wait(0.35)

        self.play(FadeOut(Group(
            image, patch_grid, patch_caption, tblock, arrow_in, arrow_out, chart,
            result_text, top5_caption,
        )))

        # Concluding summary metrics overlay.
        summary_title = Text("Measured Results Summary", font_size=28, color=WHITE_TEXT, weight=BOLD)
        summary_title.next_to(title, DOWN, buff=0.6)

        metrics = VGroup(
            Text("Kernel Speedup vs. ARM Cortex-A9:  70.0x - 97.7x", font_size=22, color=TEAL_ACCENT),
            Text("Total On-Chip Power:  1.687 W", font_size=22, color=BLUE_ACCENT),
            Text("Energy Efficiency:  2.25 GOPS/W  (205 / 220 DSPs utilized)", font_size=22, color=GOLD_ACCENT),
        ).arrange(DOWN, buff=0.4, aligned_edge=LEFT)
        metrics.next_to(summary_title, DOWN, buff=0.6)
        metrics_caveat = Text(
            "(fused matmul + softmax + GELU kernel, measured on-chip -- not a full end-to-end ViT inference speedup)",
            font_size=15, color=DIM_TEXT,
        )
        metrics_caveat.next_to(metrics, DOWN, buff=0.35)

        with self.voiceover(
            text="Measured against the ARM Cortex-A9 baseline... this fused "
                 "compute kernel -- matrix multiply, softmax, and GELU "
                 "together -- runs seventy to ninety-eight times faster in "
                 "hardware."
        ):
            self.play(Write(summary_title))
            self.play(FadeIn(metrics[0], shift=UP * 0.15))
        self.wait(0.3)

        with self.voiceover(
            text="It does this drawing just one point six eight seven "
                 "watts... for two point two five giga-operations per "
                 "second per watt, using two hundred five of the chip's "
                 "two hundred twenty available DSP slices."
        ):
            self.play(AnimationGroup(*[
                FadeIn(m, shift=UP * 0.15) for m in metrics[1:]
            ], lag_ratio=0.3), run_time=1.2)
            self.play(FadeIn(metrics_caveat))
        self.wait(0.6)

        self.play(FadeOut(VGroup(title, summary_title, metrics, metrics_caveat)))
        self.wait(0.5)


# --------------------------------------------------------------------------
# Individual scenes, for rendering/debugging one section at a time.
# Each simply reuses the corresponding TaoFPGAOverview method so the two
# never drift apart.
# --------------------------------------------------------------------------
class Scene1Introduction(VoiceoverScene, MovingCameraScene):
    def construct(self):
        configure_narration(self)
        self.camera.background_color = BG_COLOR
        TaoFPGAOverview.scene_1_introduction(self)


class Scene2SystolicArray(VoiceoverScene, MovingCameraScene):
    def construct(self):
        configure_narration(self)
        self.camera.background_color = BG_COLOR
        TaoFPGAOverview.scene_2_systolic_array(self)


class Scene3SoftmaxGelu(VoiceoverScene, MovingCameraScene):
    def construct(self):
        configure_narration(self)
        self.camera.background_color = BG_COLOR
        TaoFPGAOverview.scene_3_softmax_gelu(self)


class Scene4OutputLatency(VoiceoverScene, MovingCameraScene):
    def construct(self):
        configure_narration(self)
        self.camera.background_color = BG_COLOR
        TaoFPGAOverview.scene_4_output_latency(self)


class Scene5ViTDemo(VoiceoverScene, MovingCameraScene):
    def construct(self):
        configure_narration(self)
        self.camera.background_color = BG_COLOR
        TaoFPGAOverview.scene_5_vit_demo(self)

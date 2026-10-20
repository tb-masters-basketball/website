"""The league's look on paper, shared by every printed form (MBL-SS6 in
scoresheet.py, the paper sheet in paper_sheet.py): the bundled Barlow fonts,
the brand colours (brand/css/brand.css values), the badge and the header.

Fonts registered here, by name:
  Cond      Barlow Condensed 700  (headings, numbers)
  CondSemi  Barlow Condensed 600  (labels)
  Body      Barlow 400            (text)
  BodySemi  Barlow 600
"""
import os
from reportlab.lib.colors import HexColor
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
for _name, _file in [("Cond", "barlow-condensed-700"), ("CondSemi", "barlow-condensed-600"),
                     ("Body", "barlow-400"), ("BodySemi", "barlow-600")]:
    pdfmetrics.registerFont(TTFont(_name, os.path.join(ASSETS, "fonts", _file + ".ttf")))
BADGE = os.path.join(ASSETS, "masters-badge.png")

NAVY = HexColor("#0B1B3F")
BLUE = HexColor("#032F98")
RED = HexColor("#CB0E1D")
RULE = HexColor("#8C96AE")
TINT = HexColor("#E7ECF7")
SHADE = HexColor("#F1F3F9")

WORDMARK = "MASTERS BASKETBALL LEAGUE"


def draw_text(c, x, y, s, font="Body", size=8, color=NAVY, anchor="l", tracking=0):
    """Text at (x, y) on canvas c, anchored left, centre ("c") or right ("r").
    Returns its width."""
    c.setFillColor(color)
    w = pdfmetrics.stringWidth(s, font, size) + tracking * max(len(s) - 1, 0)
    if anchor == "c": x -= w / 2
    elif anchor == "r": x -= w
    t = c.beginText()
    t.setFont(font, size); t.setCharSpace(tracking); t.setTextOrigin(x, y)
    t.textOut(s); t.setCharSpace(0)
    c.drawText(t)
    return w


def draw_header(c, x, top, subtitle, form_line, badge=44):
    """The league header: badge, wordmark, red rule, subtitle and a small form
    line, with its top-left corner at (x, top) (PDF coordinates, y up).
    Everything scales with the badge size (44 pt on MBL-SS6)."""
    k = badge / 44
    if os.path.exists(BADGE):
        c.drawImage(BADGE, x, top - badge, badge, badge, mask="auto")
    tx = x + badge + 9 * k
    draw_text(c, tx, top - 17 * k, WORDMARK, "Cond", 17.5 * k, NAVY, tracking=0.4 * k)
    c.setFillColor(RED); c.rect(tx, top - 25 * k, 30 * k, 2 * k, stroke=0, fill=1)
    draw_text(c, tx + 36 * k, top - 26.3 * k, subtitle, "CondSemi", 8.6 * k, BLUE, tracking=0.9 * k)
    draw_text(c, tx, top - 39 * k, form_line, "Body", 6.8 * k, RULE)


def header_width(subtitle, badge=44):
    """How wide draw_header() draws (the wider of the wordmark and the subtitle line)."""
    k = badge / 44
    word = pdfmetrics.stringWidth(WORDMARK, "Cond", 17.5 * k) + 0.4 * k * (len(WORDMARK) - 1)
    sub = 36 * k + pdfmetrics.stringWidth(subtitle, "CondSemi", 8.6 * k) + 0.9 * k * (len(subtitle) - 1)
    return badge + 9 * k + max(word, sub)

"""Low-level PDF drawing primitives using fpdf2."""

from fpdf import FPDF


class DocumentBuilder:
    """Handles fpdf2 page setup and drawing primitives for intake forms.

    Letter size (8.5" x 11") with 0.75" margins. Tracks vertical cursor
    position and auto-advances after each draw call.
    """

    # Page dimensions in mm (letter size)
    PAGE_W = 215.9  # 8.5"
    PAGE_H = 279.4  # 11"
    MARGIN = 19.05   # 0.75"

    # Derived
    CONTENT_W = PAGE_W - 2 * MARGIN  # usable width

    # Font sizes
    FONT_NORMAL = 10
    FONT_SMALL = 8
    FONT_HEADING = 11
    FONT_TITLE = 12

    # Line height multiplier
    LH = 1.4

    def __init__(self):
        self.pdf = FPDF(unit="mm", format="Letter")
        self.pdf.set_auto_page_break(auto=True, margin=self.MARGIN)
        self.pdf.set_margins(self.MARGIN, self.MARGIN, self.MARGIN)
        self.pdf.add_page()
        self.y = self.MARGIN

    @property
    def usable_bottom(self) -> float:
        """Y coordinate of the bottom margin."""
        return self.PAGE_H - self.MARGIN

    def _line_h(self, font_size: float | None = None) -> float:
        """Return line height for a given font size."""
        size = font_size or self.FONT_NORMAL
        return size * 0.3528 * self.LH  # pt to mm, then multiply by LH

    def _set_font(self, style: str = "", size: float | None = None):
        size = size or self.FONT_NORMAL
        self.pdf.set_font("Helvetica", style=style, size=size)

    def check_page_break(self, needed_height: float):
        """Start a new page if remaining space is less than needed_height."""
        if self.y + needed_height > self.usable_bottom:
            self.pdf.add_page()
            self.y = self.MARGIN

    def draw_dual_facility_header(self, active_facility_key: str, facilities: dict):
        """Draw two-column header with both facilities.

        The active facility gets an X inside its checkbox rectangle.
        """
        needed = 32
        self.check_page_break(needed)

        col_w = self.CONTENT_W / 2
        start_y = self.y
        box_size = 3.5

        for i, (key, info) in enumerate(facilities.items()):
            x_start = self.MARGIN + i * col_w
            is_active = key == active_facility_key

            # Draw checkbox rectangle
            self.pdf.rect(x_start, start_y, box_size, box_size)
            if is_active:
                # Draw X inside the box
                self.pdf.set_draw_color(0, 0, 0)
                self.pdf.line(x_start + 0.5, start_y + 0.5,
                              x_start + box_size - 0.5, start_y + box_size - 0.5)
                self.pdf.line(x_start + box_size - 0.5, start_y + 0.5,
                              x_start + 0.5, start_y + box_size - 0.5)

            text_x = x_start + box_size + 2
            text_w = col_w - box_size - 4

            # Facility name (bold)
            self._set_font("B", self.FONT_NORMAL)
            self.pdf.set_xy(text_x, start_y - 0.5)
            self.pdf.cell(text_w, self._line_h(), info["name"])

            # Address
            self._set_font("", self.FONT_SMALL)
            line_h = self._line_h(self.FONT_SMALL)
            cy = start_y + self._line_h()

            self.pdf.set_xy(text_x, cy)
            self.pdf.cell(text_w, line_h, info["address"])
            cy += line_h

            self.pdf.set_xy(text_x, cy)
            self.pdf.cell(text_w, line_h, info["city_state_zip"])
            cy += line_h

            self.pdf.set_xy(text_x, cy)
            self.pdf.cell(text_w, line_h, f"Phone: {info['phone']}  Fax: {info['fax']}")

        self.y = start_y + needed
        # Thin line under header
        self.pdf.set_draw_color(180, 180, 180)
        self.pdf.line(self.MARGIN, self.y, self.MARGIN + self.CONTENT_W, self.y)
        self.pdf.set_draw_color(0, 0, 0)
        self.y += 3

    def draw_patient_id_line(self, patient_id: str):
        """Draw 'PATIENT'S ID#:' in bold with the value underlined."""
        self.check_page_break(self._line_h() + 2)
        lh = self._line_h()

        self._set_font("B", self.FONT_NORMAL)
        label = "PATIENT'S ID#: "
        label_w = self.pdf.get_string_width(label)
        self.pdf.set_xy(self.MARGIN, self.y)
        self.pdf.cell(label_w, lh, label)

        self._set_font("U", self.FONT_NORMAL)
        self.pdf.cell(0, lh, patient_id)

        self.y += lh + 2

    def draw_form_title(self, title: str):
        """Draw centered, bold, uppercase form title."""
        self.check_page_break(self._line_h(self.FONT_TITLE) + 4)
        lh = self._line_h(self.FONT_TITLE)

        self._set_font("B", self.FONT_TITLE)
        self.pdf.set_xy(self.MARGIN, self.y)
        self.pdf.cell(self.CONTENT_W, lh, title.upper(), align="C")
        self.y += lh + 4

    def draw_revision_date(self, revision_date: str):
        """Draw italic revision date in the top-right corner."""
        if not revision_date:
            return
        self._set_font("I", self.FONT_SMALL)
        text_w = self.pdf.get_string_width(revision_date) + 2
        self.pdf.set_xy(self.MARGIN + self.CONTENT_W - text_w, self.MARGIN)
        self.pdf.cell(text_w, self._line_h(self.FONT_SMALL), revision_date)

    def draw_header_note(self, text: str):
        """Draw italic smaller text for regulatory notes."""
        self.check_page_break(20)
        self._set_font("I", self.FONT_SMALL)
        lh = self._line_h(self.FONT_SMALL)
        for line in text.split("\n"):
            self.pdf.set_xy(self.MARGIN, self.y)
            self.pdf.cell(self.CONTENT_W, lh, line, align="C")
            self.y += lh
        self.y += 2

    def draw_paragraph(self, text: str):
        """Draw word-wrapped body text within margins."""
        self._set_font("", self.FONT_NORMAL)
        lh = self._line_h()
        # Estimate height for page break check
        chars_per_line = max(1, int(self.CONTENT_W / (self.FONT_NORMAL * 0.2)))
        est_lines = max(1, len(text) // chars_per_line + 1)
        self.check_page_break(est_lines * lh + 2)

        self.pdf.set_xy(self.MARGIN, self.y)
        self.pdf.multi_cell(self.CONTENT_W, lh, text)
        self.y = self.pdf.get_y() + 2

    def draw_section_heading(self, heading: str):
        """Draw bold heading text."""
        self._set_font("B", self.FONT_HEADING)
        lh = self._line_h(self.FONT_HEADING)
        # Estimate lines for multi-line headings
        heading_w = self.pdf.get_string_width(heading)
        est_lines = max(1, int(heading_w / self.CONTENT_W) + 1)
        self.check_page_break(est_lines * lh + 2)

        self.pdf.set_xy(self.MARGIN, self.y)
        self.pdf.multi_cell(self.CONTENT_W, lh, heading)
        self.y = self.pdf.get_y() + 1

    def draw_text_field(self, label: str, value: str, width: float | None = None,
                        x_offset: float | None = None):
        """Draw bold label followed by value on an underline."""
        w = width or self.CONTENT_W
        x = x_offset if x_offset is not None else self.MARGIN
        lh = self._line_h()
        self.check_page_break(lh + 2)

        if label:
            self._set_font("B", self.FONT_NORMAL)
            label_text = f"{label}: "
            label_w = self.pdf.get_string_width(label_text)
            self.pdf.set_xy(x, self.y)
            self.pdf.cell(label_w, lh, label_text)
        else:
            label_w = 0

        # Draw underline for value area
        value_x = x + label_w
        value_w = w - label_w
        self._set_font("", self.FONT_NORMAL)
        self.pdf.set_xy(value_x, self.y)
        self.pdf.cell(value_w, lh, value, border="B")

    def draw_textarea(self, value: str, num_lines: int = 4):
        """Render value as paragraph or draw blank lines if empty."""
        lh = self._line_h()
        if value:
            self.draw_paragraph(value)
        else:
            self.check_page_break(num_lines * lh + 2)
            for _ in range(num_lines):
                self.pdf.set_draw_color(180, 180, 180)
                self.pdf.line(self.MARGIN, self.y + lh,
                              self.MARGIN + self.CONTENT_W, self.y + lh)
                self.y += lh
            self.pdf.set_draw_color(0, 0, 0)
            self.y += 2

    def draw_radio_field(self, label: str, options: list, selected: str):
        """Draw horizontal radio buttons with drawn circles."""
        lh = self._line_h()
        self.check_page_break(lh + 4)

        x = self.MARGIN
        if label:
            self._set_font("B", self.FONT_NORMAL)
            self.pdf.set_xy(x, self.y)
            label_text = f"{label}: "
            label_w = self.pdf.get_string_width(label_text)
            self.pdf.cell(label_w, lh, label_text)
            x += label_w + 2

        self._set_font("", self.FONT_NORMAL)
        radius = 2.0
        for option in options:
            # Draw circle
            cx = x + radius
            cy = self.y + lh / 2
            self.pdf.circle(cx, cy, radius)
            if option == selected:
                # Fill circle for selected option
                self.pdf.set_fill_color(0, 0, 0)
                self.pdf.circle(cx, cy, radius - 0.6, style="F")
                self.pdf.set_fill_color(255, 255, 255)

            # Option label
            self.pdf.set_xy(x + radius * 2 + 1.5, self.y)
            opt_w = self.pdf.get_string_width(option) + 6
            self.pdf.cell(opt_w, lh, option)
            x += radius * 2 + 1.5 + opt_w + 4

        self.y += lh + 2

    def draw_checkbox_field(self, label: str, options: list, checked: list):
        """Draw vertical checkboxes with drawn rectangles."""
        lh = self._line_h()
        needed = lh * (len(options) + (1 if label else 0)) + 4
        self.check_page_break(needed)

        if label:
            self._set_font("B", self.FONT_NORMAL)
            self.pdf.set_xy(self.MARGIN, self.y)
            self.pdf.cell(self.CONTENT_W, lh, label)
            self.y += lh

        box_size = 3.5
        self._set_font("", self.FONT_NORMAL)
        for option in options:
            # Draw checkbox rectangle
            bx = self.MARGIN + 2
            by = self.y + (lh - box_size) / 2
            self.pdf.rect(bx, by, box_size, box_size)

            if option in (checked or []):
                # Draw X inside
                self.pdf.line(bx + 0.5, by + 0.5,
                              bx + box_size - 0.5, by + box_size - 0.5)
                self.pdf.line(bx + box_size - 0.5, by + 0.5,
                              bx + 0.5, by + box_size - 0.5)

            self.pdf.set_xy(bx + box_size + 2, self.y)
            self.pdf.cell(0, lh, option)
            self.y += lh

        self.y += 2

    def draw_signature_block(self, signer_role: str, include_date: bool = True):
        """Draw signature line with role label below, plus optional date line."""
        needed = 20
        self.check_page_break(needed)
        self.y += 6  # spacing above signature

        lh = self._line_h()
        sig_w = self.CONTENT_W * 0.55 if include_date else self.CONTENT_W * 0.8
        sig_x = self.MARGIN

        # Signature line
        self.pdf.set_draw_color(0, 0, 0)
        self.pdf.line(sig_x, self.y, sig_x + sig_w, self.y)

        # Role label below
        self._set_font("", self.FONT_SMALL)
        self.pdf.set_xy(sig_x, self.y + 1)
        self.pdf.cell(sig_w, self._line_h(self.FONT_SMALL), signer_role)

        if include_date:
            date_x = sig_x + sig_w + 15
            date_w = self.MARGIN + self.CONTENT_W - date_x
            # Date line
            self.pdf.line(date_x, self.y, date_x + date_w, self.y)
            self.pdf.set_xy(date_x, self.y + 1)
            self.pdf.cell(date_w, self._line_h(self.FONT_SMALL), "Date")

        self.y += self._line_h(self.FONT_SMALL) + 6

    def draw_horizontal_rule(self):
        """Draw a thin separator line."""
        self.check_page_break(4)
        self.pdf.set_draw_color(180, 180, 180)
        self.pdf.line(self.MARGIN, self.y, self.MARGIN + self.CONTENT_W, self.y)
        self.pdf.set_draw_color(0, 0, 0)
        self.y += 3

    def get_bytes(self) -> bytes:
        """Return the PDF document as bytes."""
        return self.pdf.output()

    def save(self, filepath: str):
        """Write the PDF document to a file."""
        self.pdf.output(filepath)

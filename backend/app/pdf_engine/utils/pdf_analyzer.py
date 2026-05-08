"""PDF Analyzer for semi-automatic form field detection.

Analyzes PDF documents to detect potential form fields such as:
- Blank underlines (text input fields)
- Checkbox squares
- Signature lines
- Text labels that suggest form fields
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

import pdfplumber


@dataclass
class DetectedField:
    """A detected potential form field from PDF analysis."""

    suggested_id: str  # e.g., "patient_name" from nearby label
    field_type: str  # text, checkbox, signature, date
    page: int  # 0-indexed page number
    x: float  # X coordinate (points from left)
    y: float  # Y coordinate (points from bottom of page)
    width: float  # Field width in points
    height: float  # Field height in points
    confidence: float  # 0-1, how confident the detection is
    nearby_text: str  # Context for manual review
    label: str = ""  # Detected label text

    def to_dict(self) -> dict:
        return {
            "suggested_id": self.suggested_id,
            "field_type": self.field_type,
            "page": self.page,
            "x": round(self.x, 2),
            "y": round(self.y, 2),
            "width": round(self.width, 2),
            "height": round(self.height, 2),
            "confidence": round(self.confidence, 2),
            "nearby_text": self.nearby_text,
            "label": self.label,
        }


@dataclass
class AnalysisResult:
    """Result of PDF analysis."""

    pdf_path: str
    page_count: int
    detected_fields: list = field(default_factory=list)  # list of DetectedField
    errors: list = field(default_factory=list)  # list of error messages

    def to_dict(self) -> dict:
        return {
            "pdf_path": self.pdf_path,
            "page_count": self.page_count,
            "detected_fields": [f.to_dict() for f in self.detected_fields],
            "errors": self.errors,
        }


def slugify(text: str) -> str:
    """Convert text to a valid field ID slug."""
    # Remove special characters, convert spaces to underscores
    # Normalize curly apostrophes
    text = text.lower().strip().replace("’", "'").replace("‘", "'")
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s-]+", "_", text)
    return text[:50]  # Limit length


class PDFAnalyzer:
    """Analyzes PDFs to detect potential form fields."""

    # Common label patterns that indicate form fields
    LABEL_PATTERNS = [
        r"patient\s*(?:name|id|signature)",
        r"date(?:\s*of\s*birth)?",
        r"name\s*(?:of|:)",
        r"signature",
        r"address",
        r"phone",
        r"counselor",
        r"medical\s*director",
        r"witness",
        r"(?:admission|discharge)\s*date",
    ]

    # Minimum dimensions for detected fields (in points)
    MIN_FIELD_WIDTH = 50
    MIN_FIELD_HEIGHT = 10
    DEFAULT_FIELD_HEIGHT = 18

    def __init__(self, pdf_path: str | Path):
        self.pdf_path = Path(pdf_path)
        if not self.pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {self.pdf_path}")

    def analyze(self) -> AnalysisResult:
        """
        Analyze the PDF and detect potential form fields.

        Returns:
            AnalysisResult with detected fields and metadata.
        """
        result = AnalysisResult(
            pdf_path=str(self.pdf_path),
            page_count=0,
            detected_fields=[],
            errors=[],
        )

        try:
            with pdfplumber.open(self.pdf_path) as pdf:
                result.page_count = len(pdf.pages)

                for page_num, page in enumerate(pdf.pages):
                    page_height = page.height
                    page_width = page.width

                    # Extract text with positions
                    words = page.extract_words(
                        keep_blank_chars=True,
                        x_tolerance=3,
                        y_tolerance=3,
                    )

                    # Extract geometric objects from the page
                    lines = page.objects.get("line", [])
                    curves = page.objects.get("curve", [])
                    rects = page.objects.get("rect", [])
                    all_line_objects = lines + curves

                    # Detect fields from text patterns
                    text_fields = self._detect_text_fields(
                        words, page_num, page_height, page_width
                    )
                    result.detected_fields.extend(text_fields)

                    # Detect underlines (potential text input fields)
                    underline_fields = self._detect_underlines(
                        all_line_objects, words, page_num, page_height
                    )
                    result.detected_fields.extend(underline_fields)

                    # Detect checkboxes from rectangles
                    checkbox_fields = self._detect_checkboxes(
                        rects, words, page_num, page_height
                    )
                    result.detected_fields.extend(checkbox_fields)

                    # Detect signature lines
                    signature_fields = self._detect_signatures(
                        all_line_objects, rects, words, page_num, page_height
                    )
                    result.detected_fields.extend(signature_fields)

                    # Detect date boxes
                    date_box_fields = self._detect_date_boxes(
                        rects, words, page_num, page_height
                    )
                    result.detected_fields.extend(date_box_fields)

                    # Aggressively detect signatures from keywords as a fallback
                    keyword_sig_fields = self._detect_signatures_from_keywords(
                        words, page_num, page_height, page_width
                    )
                    result.detected_fields.extend(keyword_sig_fields)

        except Exception as e:
            result.errors.append(f"Error analyzing PDF: {str(e)}")

        # Remove duplicates and sort by page, then y position (top to bottom)
        result.detected_fields = self._deduplicate_fields(result.detected_fields)
        result.detected_fields.sort(key=lambda f: (f.page, -f.y, f.x))

        return result

    def _detect_text_fields(
        self, words: list, page_num: int, page_height: float, page_width: float
    ) -> list[DetectedField]:
        """Detect potential text fields based on label patterns."""
        fields = []

        # Build text lines from words
        lines_of_text = self._group_words_into_lines(words)

        for line_words in lines_of_text:
            line_text = " ".join(w["text"] for w in line_words)
            line_lower = line_text.lower()

            # Check for label patterns
            for pattern in self.LABEL_PATTERNS:
                if re.search(pattern, line_lower):
                    # Found a label - create a field to the right or below
                    last_word = line_words[-1]

                    # Check if line ends with colon (field to the right)
                    if line_text.rstrip().endswith(":"):
                        field_x = last_word["x1"] + 5
                        field_y = page_height - last_word["top"] - self.DEFAULT_FIELD_HEIGHT
                        field_width = page_width - field_x - 72  # Leave margin
                    else:
                        # Field likely below
                        field_x = line_words[0]["x0"]
                        field_y = page_height - last_word["bottom"] - self.DEFAULT_FIELD_HEIGHT - 5
                        field_width = 200

                    if field_width >= self.MIN_FIELD_WIDTH:
                        suggested_id = slugify(line_text.replace(":", "").strip())
                        if suggested_id:
                            fields.append(
                                DetectedField(
                                    suggested_id=suggested_id,
                                    field_type=self._infer_field_type(line_lower),
                                    page=page_num,
                                    x=field_x,
                                    y=field_y,
                                    width=field_width,
                                    height=self.DEFAULT_FIELD_HEIGHT,
                                    confidence=0.6,
                                    nearby_text=line_text[:100],
                                    label=line_text.replace(":", "").strip(),
                                )
                            )
                    break

        return fields

    def _detect_underlines(
        self, lines: list, words: list, page_num: int, page_height: float
    ) -> list[DetectedField]:
        """Detect horizontal lines that may be form field underlines."""
        fields = []

        for line in lines:
            # Check if it's a horizontal line (underline)
            if abs(line.get("top", 0) - line.get("bottom", 0)) < 2:
                x0 = line.get("x0", 0)
                x1 = line.get("x1", 0)
                width = x1 - x0

                if width >= self.MIN_FIELD_WIDTH:
                    # Look for label text to the left or above
                    line_y = line.get("top", 0)
                    label = self._find_nearby_label(words, x0, line_y, "left")

                    suggested_id = slugify(label) if label else f"field_page{page_num}_{int(x0)}"

                    fields.append(
                        DetectedField(
                            suggested_id=suggested_id,
                            field_type="text",
                            page=page_num,
                            x=x0,
                            y=page_height - line_y - self.DEFAULT_FIELD_HEIGHT,
                            width=width,
                            height=self.DEFAULT_FIELD_HEIGHT,
                            confidence=0.7,
                            nearby_text=label or "Underline detected",
                            label=label or "",
                        )
                    )

        return fields

    def _detect_checkboxes(
        self, rects: list, words: list, page_num: int, page_height: float
    ) -> list[DetectedField]:
        """Detect small squares that may be checkboxes."""
        fields = []

        for rect in rects:
            width = rect.get("width", rect.get("x1", 0) - rect.get("x0", 0))
            height = rect.get("height", rect.get("bottom", 0) - rect.get("top", 0))

            # Checkboxes are typically small squares (8-20 points)
            if 6 <= width <= 25 and 6 <= height <= 25 and abs(width - height) < 5:
                x = rect.get("x0", 0)
                y = rect.get("top", 0)

                # Look for label text to the right
                label = self._find_nearby_label(words, x + width, y, "right")

                suggested_id = slugify(label) if label else f"checkbox_page{page_num}_{int(x)}"

                fields.append(
                    DetectedField(
                        suggested_id=suggested_id,
                        field_type="checkbox",
                        page=page_num,
                        x=x,
                        y=page_height - y - height,
                        width=width,
                        height=height,
                        confidence=0.8,
                        nearby_text=label or "Checkbox detected",
                        label=label or "",
                    )
                )

        return fields

    def _detect_signatures(
        self, lines: list, rects: list, words: list, page_num: int, page_height: float
    ) -> list[DetectedField]:
        """Detect long horizontal lines or boxes near 'signature' text."""
        fields = []
        signature_keywords = ["signature", "sign here", "signed", "witness"]

        # Find all words containing signature keywords
        signature_locations = []
        for word in words:
            # Normalize text and use regex for whole-word matching
            clean_text = word["text"].lower().replace("’", "'")
            if any(re.search(r"\b" + re.escape(kw) + r"\b", clean_text) for kw in signature_keywords):
                signature_locations.append(word)

        if not signature_locations:
            return []

        # Combine graphical lines and text-based underlines (e.g., "____")
        all_lines = []
        for line in lines:
            if abs(line.get("top", 0) - line.get("bottom", 0)) < 2:
                all_lines.append(line)
        for word in words:
            if len(word["text"]) > 10 and all(c == "_" for c in word["text"]):
                all_lines.append({
                    "x0": word["x0"], "x1": word["x1"], "top": word["top"], "bottom": word["bottom"]
                })

        # Look for long lines near signature text
        for line in all_lines:
            width = line.get("x1", 0) - line.get("x0", 0)

            # Signature lines are typically longer (> 150 points)
            if width >= 150:
                line_y = line.get("top", 0)
                x0 = line.get("x0", 0)

                # Check if near a signature keyword
                for sig_word in signature_locations:
                    # Keyword should be close to the line, usually to the left
                    is_nearby_left = sig_word["x1"] < x0 + 20  # Keyword ends before or just after line starts
                    is_vertically_close = abs(sig_word["top"] - line_y) < 40  # Generous vertical tolerance
                    is_horizontally_close = abs(x0 - sig_word["x1"]) < 150  # Keyword not too far left

                    if is_nearby_left and is_vertically_close and is_horizontally_close:
                        # Build the label by finding contiguous words to the left of the keyword.
                        phrase_words = [sig_word]
                        current_word = sig_word
                        # Search for words to the left, up to a reasonable limit
                        for _ in range(10):  # Limit search to 10 words to prevent infinite loops
                            # Find candidate words to the immediate left of the current phrase
                            candidates = [ 
                                w
                                for w in words
                                if w["x1"] < current_word["x0"] and abs(w["top"] - current_word["top"]) < 20 # Increased vertical tolerance
                            ]
                            if not candidates:
                                break

                            # Find the closest word
                            closest_word = min(candidates, key=lambda w: current_word["x0"] - w["x1"])

                            # If it's too far away, stop.
                            if (current_word["x0"] - closest_word["x1"]) > 25:  # Max space between words
                                break

                            phrase_words.insert(0, closest_word)
                            current_word = closest_word

                        label_text = " ".join(w["text"] for w in phrase_words).strip()

                        suggested_id = slugify(label_text) + "_signature"

                        fields.append(
                            DetectedField(
                                suggested_id=suggested_id,
                                field_type="signature",
                                page=page_num,
                                x=x0, y=page_height - line_y - 20, width=width, height=40,
                                confidence=0.9,
                                nearby_text=f"Signature line near '{label_text}'",
                                label=label_text,
                            )
                        )
                        break

        # Look for 'X' markers for signatures (e.g., "Signature X____")
        for word in words:
            if word["text"].strip().upper() == "X" and (word["x1"] - word["x0"]) < 25:
                x_marker = word
                # Find all words in a region above or to the left of the X
                region_nearby = [
                    w for w in words
                    if (
                        # Above
                        (w["bottom"] < x_marker["top"] and abs(x_marker["top"] - w["bottom"]) < 50 and abs(w["x0"] - x_marker["x0"]) < 200) or
                        # Left
                        (w["x1"] < x_marker["x0"] and abs(x_marker["x0"] - w["x1"]) < 150 and abs(w["top"] - x_marker["top"]) < 20)
                    )
                ]

                if not region_nearby:
                    continue

                # Check if any of these words are signature keywords
                if any(
                    any(re.search(r"\b" + re.escape(kw) + r"\b", w["text"].lower().replace("’", "'")) for kw in signature_keywords)
                    for w in region_nearby
                ):
                    # Group nearby words into lines to find the label
                    lines_nearby = self._group_words_into_lines(region_nearby)
                    if not lines_nearby:
                        continue

                    # Assume the last line before the 'X' is the label
                    lines_nearby.sort(key=lambda line: line[0]["top"])
                    label_text = " ".join(w["text"] for w in lines_nearby[-1])
                    suggested_id = slugify(label_text) + "_signature"

                    # Define field boundaries around the 'X', extending to the right
                    fields.append(
                        DetectedField(
                            suggested_id=suggested_id, field_type="signature", page=page_num,
                            x=x_marker["x0"], y=page_height - x_marker["bottom"] - 10,
                            width=(x_marker["x1"] - x_marker["x0"]) + 150, height=40,
                            confidence=0.8, nearby_text=f"Signature X near '{label_text}'", label=label_text,
                        )
                    )

        # Look for signature boxes (rectangles)
        for rect in rects:
            width = rect.get("width", rect.get("x1", 0) - rect.get("x0", 0))
            height = rect.get("height", rect.get("bottom", 0) - rect.get("top", 0))

            # Signature boxes are reasonably large rectangles, but not whole page boxes
            if width > 100 and 20 < height < 100:
                x0 = rect.get("x0", 0)
                top = rect.get("top", 0)
                bottom = rect.get("bottom", 0)

                # Check if near a signature keyword
                for sig_word in signature_locations:
                    # Keyword should be close to the box, usually above or to the left
                    is_above = sig_word["bottom"] < top and abs(top - sig_word["bottom"]) < 30
                    is_left = sig_word["x1"] < x0 and abs(x0 - sig_word["x1"]) < 10

                    # Check vertical alignment for left-side labels
                    is_aligned = abs(sig_word["top"] - top) < height

                    if (is_above and abs(sig_word["x0"] - x0) < 50) or (is_left and is_aligned):
                        label_text = sig_word["text"]

                        # Try to find a more specific label
                        if is_above:
                            label_text = self._find_nearby_label(words, x0, top, "above") or label_text
                        elif is_left:
                            label_text = self._find_nearby_label(words, x0, top, "left") or label_text

                        suggested_id = slugify(label_text) + "_signature"

                        fields.append(
                            DetectedField(
                                suggested_id=suggested_id,
                                field_type="signature",
                                page=page_num,
                                x=x0,
                                y=page_height - bottom,
                                width=width,
                                height=height,
                                confidence=0.85,
                                nearby_text=f"Signature box near '{label_text}'",
                                label=label_text,
                            )
                        )
                        break  # Found a keyword for this rect, move to next rect

        return fields

    def _detect_date_boxes(
        self, rects: list, words: list, page_num: int, page_height: float
    ) -> list[DetectedField]:
        """Detect boxes near 'date' text."""
        fields = []
        date_keywords = ["date"]

        # Find all words containing date keywords
        date_locations = []
        for word in words:
            if any(kw in word["text"].lower() for kw in date_keywords):
                date_locations.append(word)

        if not date_locations:
            return []

        # Look for date boxes (rectangles)
        for rect in rects:
            width = rect.get("width", rect.get("x1", 0) - rect.get("x0", 0))
            height = rect.get("height", rect.get("bottom", 0) - rect.get("top", 0))

            # Date boxes are smaller than signature boxes
            if width > 50 and 15 < height < 50:
                x0 = rect.get("x0", 0)
                top = rect.get("top", 0)
                bottom = rect.get("bottom", 0)

                # Check if near a date keyword
                for date_word in date_locations:
                    # Keyword should be close to the box, usually above or to the left
                    is_above = date_word["bottom"] < top and abs(top - date_word["bottom"]) < 30
                    is_left = date_word["x1"] < x0 and abs(x0 - date_word["x1"]) < 10

                    # Check vertical alignment for left-side labels
                    is_aligned = abs(date_word["top"] - top) < height

                    if (is_above and abs(date_word["x0"] - x0) < 50) or (is_left and is_aligned):
                        label_text = date_word["text"]

                        # Try to find a more specific label
                        if is_above:
                            label_text = self._find_nearby_label(words, x0, top, "above") or label_text
                        elif is_left:
                            label_text = self._find_nearby_label(words, x0, top, "left") or label_text

                        suggested_id = slugify(label_text) + "_date"

                        fields.append(
                            DetectedField(
                                suggested_id=suggested_id,
                                field_type="date",
                                page=page_num,
                                x=x0,
                                y=page_height - bottom,
                                width=width,
                                height=height,
                                confidence=0.85,
                                nearby_text=f"Date box near '{label_text}'",
                                label=label_text,
                            )
                        )
                        break  # Found a keyword for this rect, move to next rect

        return fields

    def _detect_signatures_from_keywords(
        self, words: list, page_num: int, page_height: float, page_width: float
    ) -> list[DetectedField]:
        """
        Aggressively detect signature fields based only on keywords.

        This is a fallback for when no line, box, or 'X' is found.
        It finds a keyword and places a field to its right.
        """
        fields = []
        signature_keywords = ["signature", "sign here", "signed", "witness"]

        for word in words:
            clean_text = word["text"].lower().replace("’", "'")
            if any(re.search(r"\b" + re.escape(kw) + r"\b", clean_text) for kw in signature_keywords):

                # We found a keyword. Let's try to get a slightly better label than just the word.
                label = self._find_nearby_label(words, word["x0"], word["top"], "left")
                label_text = f"{label} {word['text']}" if label else word['text']

                # Place a field to the right of the keyword.
                field_x = word["x1"] + 5
                field_y_pdf = word["top"]

                field_width = 200  # A standard width for a signature
                if field_x + field_width > page_width - 20:  # Respect right margin
                    field_width = page_width - field_x - 20

                field_height = 40  # Standard signature height

                # Convert y from pdfplumber (top-down) to our (bottom-up)
                field_y = page_height - field_y_pdf - field_height

                suggested_id = slugify(label_text) + "_signature"

                fields.append(
                    DetectedField(
                        suggested_id=suggested_id, field_type="signature", page=page_num,
                        x=field_x, y=field_y, width=field_width, height=field_height,
                        confidence=0.4,  # Low confidence to be overridden by other methods
                        nearby_text=f"Keyword-based: '{label_text}'",
                        label=label_text.strip(),
                    )
                )
        return fields

    def _group_words_into_lines(self, words: list) -> list[list]:
        """Group words into lines based on Y position."""
        if not words:
            return []

        # Sort by Y position (top), then X position
        sorted_words = sorted(words, key=lambda w: (w["top"], w["x0"]))

        lines = []
        current_line = [sorted_words[0]]
        current_top = sorted_words[0]["top"]

        for word in sorted_words[1:]:
            # Same line if Y position within 5 points
            if abs(word["top"] - current_top) < 5:
                current_line.append(word)
            else:
                lines.append(current_line)
                current_line = [word]
                current_top = word["top"]

        if current_line:
            lines.append(current_line)

        return lines

    def _find_nearby_label(
        self, words: list, x: float, y: float, direction: str
    ) -> str | None:
        """Find label text near a position."""
        candidates = []

        for word in words:
            word_x = word["x0"]
            word_y = word["top"]

            if direction == "left":
                # Look for text to the left and roughly same Y
                if word_x < x and abs(word_y - y) < 20: # Increased vertical tolerance
                    distance = x - word["x1"]
                    if distance < 100:  # Within 100 points
                        candidates.append((distance, word["text"]))
            elif direction == "right":
                # Look for text to the right and roughly same Y
                if word_x > x and abs(word_y - y) < 20: # Increased vertical tolerance
                    distance = word_x - x
                    if distance < 100:
                        candidates.append((distance, word["text"]))
            elif direction == "above":
                # Look for text above
                if word_y < y and abs(word_x - x) < 100: # Increased horizontal tolerance
                    distance = y - word["bottom"]
                    if distance < 30:
                        candidates.append((distance, word["text"]))

        if candidates:
            # Return the closest text
            candidates.sort(key=lambda c: c[0])
            return candidates[0][1]

        return None

    def _infer_field_type(self, text: str) -> str:
        """Infer field type from label text."""
        text = text.lower().replace("’", "'")
        if "date" in text:
            return "date"
        if "signature" in text:
            return "signature"
        if any(word in text for word in ["check", "select", "choose"]):
            return "checkbox"
        return "text"

    def _deduplicate_fields(
        self, fields: list[DetectedField]
    ) -> list[DetectedField]:
        """Remove duplicate or overlapping fields."""
        if not fields:
            return []

        # Sort by confidence (descending) so we keep higher confidence fields
        fields.sort(key=lambda f: -f.confidence)

        unique = []
        for f in fields:
            is_duplicate = False
            for existing in unique:
                if existing.page != f.page:
                    continue
                # Check for overlap
                if self._fields_overlap(f, existing):
                    is_duplicate = True
                    break
            if not is_duplicate:
                unique.append(f)

        return unique

    def _fields_overlap(self, f1: DetectedField, f2: DetectedField) -> bool:
        """Check if two fields overlap significantly."""
        # Calculate overlap area
        x_overlap = max(0, min(f1.x + f1.width, f2.x + f2.width) - max(f1.x, f2.x))
        y_overlap = max(0, min(f1.y + f1.height, f2.y + f2.height) - max(f1.y, f2.y))
        overlap_area = x_overlap * y_overlap

        # Calculate smaller field area
        f1_area = f1.width * f1.height
        f2_area = f2.width * f2.height
        smaller_area = min(f1_area, f2_area)

        # Overlap if > 50% of smaller field
        return overlap_area > 0.5 * smaller_area if smaller_area > 0 else False


def analyze_pdf(pdf_path: str | Path) -> AnalysisResult:
    """Convenience function to analyze a PDF."""
    analyzer = PDFAnalyzer(pdf_path)
    return analyzer.analyze()

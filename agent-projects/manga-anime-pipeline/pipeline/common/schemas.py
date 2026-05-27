from __future__ import annotations

WORKFLOW_ROUTES = [
    "establish_scene",
    "dialogue_light_motion",
    "dialogue_heavy_expression",
    "action_performance",
    "transition_atmosphere",
    "repair_only",
    "skip",
]

BOX_SCHEMA = {
    "type": "array",
    "items": {"type": "integer"},
    "minItems": 4,
    "maxItems": 4,
}

OCR_BLOCK_SCHEMA = {
    "type": "object",
    "required": ["block_id", "text", "box", "confidence", "language"],
    "properties": {
        "block_id": {"type": "string"},
        "text": {"type": "string"},
        "box": BOX_SCHEMA,
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "language": {"type": "string"},
    },
}

OCR_RESULT_SCHEMA = {
    "type": "object",
    "required": ["ocr_blocks", "reading_order", "layout_blocks"],
    "properties": {
        "ocr_blocks": {"type": "array", "items": OCR_BLOCK_SCHEMA},
        "reading_order": {"type": "array", "items": {"type": "string"}},
        "layout_blocks": {"type": "array"},
    },
}

CHAPTER_SCHEMA = {
    "type": "object",
    "required": ["series_id", "chapter_id", "pages"],
    "properties": {
        "series_id": {"type": "string"},
        "chapter_id": {"type": "string"},
        "input_type": {"type": "string"},
        "pages": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["page_id", "image_path", "width", "height"],
                "properties": {
                    "page_id": {"type": "string"},
                    "image_path": {"type": "string"},
                    "width": {"type": "integer", "minimum": 1},
                    "height": {"type": "integer", "minimum": 1},
                },
            },
        },
    },
}

WINDOW_MANIFEST_SCHEMA = {
    "type": "object",
    "required": ["series_id", "chapter_id", "windows"],
    "properties": {
        "series_id": {"type": "string"},
        "chapter_id": {"type": "string"},
        "generated_at": {"type": "string"},
        "window_height": {"type": "integer"},
        "overlap": {"type": "integer"},
        "windows": {
            "type": "array",
            "items": {
                "type": "object",
                "required": [
                    "window_id",
                    "page_id",
                    "source_page",
                    "image_path",
                    "source_box",
                    "overlap_prev",
                    "overlap_next",
                    "width",
                    "height",
                ],
                "properties": {
                    "window_id": {"type": "string"},
                    "page_id": {"type": "string"},
                    "source_page": {"type": "string"},
                    "image_path": {"type": "string"},
                    "source_box": BOX_SCHEMA,
                    "overlap_prev": {"type": "integer", "minimum": 0},
                    "overlap_next": {"type": "integer", "minimum": 0},
                    "width": {"type": "integer", "minimum": 1},
                    "height": {"type": "integer", "minimum": 1},
                    "index": {"type": "integer", "minimum": 0},
                },
            },
        },
    },
}

STRUCTURED_PACKET_SCHEMA = {
    "type": "object",
    "required": [
        "window_id",
        "page_id",
        "source_box",
        "ocr_blocks",
        "reading_order",
        "layout_blocks",
        "dialogue_blocks",
        "bubble_boxes",
        "sfx_blocks",
        "cleaned_text_candidates",
        "object_boxes",
        "object_masks",
        "crop_candidates",
        "focus_subjects",
        "scene_density",
    ],
    "properties": {
        "series_id": {"type": "string"},
        "chapter_id": {"type": "string"},
        "window_id": {"type": "string"},
        "page_id": {"type": "string"},
        "window_image_path": {"type": "string"},
        "source_box": BOX_SCHEMA,
        "ocr_blocks": {"type": "array", "items": OCR_BLOCK_SCHEMA},
        "reading_order": {"type": "array", "items": {"type": "string"}},
        "layout_blocks": {"type": "array"},
        "dialogue_blocks": {"type": "array"},
        "bubble_boxes": {"type": "array"},
        "sfx_blocks": {"type": "array"},
        "cleaned_text_candidates": {"type": "array"},
        "object_boxes": {"type": "array"},
        "object_masks": {"type": "array"},
        "crop_candidates": {"type": "array"},
        "focus_subjects": {"type": "array"},
        "scene_density": {"type": ["number", "object"]},
    },
}

SHOT_SCHEMA = {
    "type": "object",
    "required": [
        "shot_id",
        "source_pages",
        "source_windows",
        "source_ranges",
        "merge_with_prev",
        "merge_with_next",
        "story_role",
        "shot_type",
        "anime_fit_score",
        "main_characters",
        "support_characters",
        "emotion",
        "action_level",
        "dialogue_summary",
        "continuity_notes",
        "crop_recommendation",
        "positive_prompt",
        "negative_prompt",
        "style_anchor",
        "workflow_route",
        "confidence",
    ],
    "properties": {
        "shot_id": {"type": "string"},
        "source_pages": {"type": "array", "items": {"type": "string"}, "minItems": 1},
        "source_windows": {"type": "array", "items": {"type": "string"}, "minItems": 1},
        "source_ranges": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["page_id", "box"],
                "properties": {"page_id": {"type": "string"}, "box": BOX_SCHEMA},
            },
            "minItems": 1,
        },
        "merge_with_prev": {"type": "boolean"},
        "merge_with_next": {"type": "boolean"},
        "story_role": {"type": "string"},
        "shot_type": {"type": "string"},
        "anime_fit_score": {"type": "number", "minimum": 0, "maximum": 1},
        "main_characters": {"type": "array", "items": {"type": "string"}},
        "support_characters": {"type": "array", "items": {"type": "string"}},
        "emotion": {"type": "string"},
        "action_level": {"type": "string"},
        "dialogue_summary": {"type": "string"},
        "continuity_notes": {"type": "array", "items": {"type": "string"}},
        "crop_recommendation": {"type": "object"},
        "positive_prompt": {"type": "string"},
        "negative_prompt": {"type": "string"},
        "style_anchor": {"type": "string"},
        "workflow_route": {"type": "string", "enum": WORKFLOW_ROUTES},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    },
}

SHOT_MANIFEST_SCHEMA = {
    "type": "object",
    "required": ["manifest_version", "series_id", "chapter_id", "generated_at", "shots"],
    "properties": {
        "manifest_version": {"type": "string"},
        "series_id": {"type": "string"},
        "chapter_id": {"type": "string"},
        "generated_at": {"type": "string"},
        "director": {"type": "object"},
        "source_packet_refs": {"type": "array", "items": {"type": "string"}},
        "shots": {"type": "array", "items": SHOT_SCHEMA},
    },
}

TASK_STATUS_SCHEMA = {
    "type": "object",
    "required": [
        "task_id",
        "stage",
        "status",
        "started_at",
        "finished_at",
        "input_refs",
        "output_refs",
        "error_message",
        "retry_count",
    ],
    "properties": {
        "task_id": {"type": "string"},
        "stage": {"type": "string"},
        "status": {"type": "string"},
        "started_at": {"type": "string"},
        "finished_at": {"type": ["string", "null"]},
        "input_refs": {"type": "array", "items": {"type": "string"}},
        "output_refs": {"type": "array", "items": {"type": "string"}},
        "error_message": {"type": ["string", "null"]},
        "retry_count": {"type": "integer", "minimum": 0},
    },
}

STAGE1_STATUS_SCHEMA = {
    "type": "object",
    "required": ["run_id", "series_id", "chapter_id", "overall_status", "started_at", "finished_at", "outputs", "statuses"],
    "properties": {
        "run_id": {"type": "string"},
        "series_id": {"type": "string"},
        "chapter_id": {"type": "string"},
        "overall_status": {"type": "string"},
        "started_at": {"type": "string"},
        "finished_at": {"type": "string"},
        "outputs": {"type": "object"},
        "counts": {"type": "object"},
        "error_message": {"type": "string"},
        "statuses": {"type": "array", "items": TASK_STATUS_SCHEMA},
    },
}


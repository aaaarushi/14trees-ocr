"""
=============================================================================
EXTRACTION SCHEMA CONFIGURATION
=============================================================================

This file defines all fields extracted from documents. Update this file when:
- Adding new fields to your Document AI custom extractor
- Removing fields
- Changing field order
- Renaming fields

The order of fields here determines:
- Column order in Google Sheets
- Property order in Notion database
- Field processing order

=============================================================================
FIELD TYPES:
- "text"     → Text/string values (including Devanagari script)
- "number"   → Numeric values (integers or decimals)
- "checkbox" → Boolean/yes-no values
=============================================================================
"""

# Your extraction schema - edit this list to update fields everywhere
FIELDS = [
    {
        "name": "serial_number",              # Document AI field name (must match extractor)
        "type": "number",                     # Field type: text, number, or checkbox
        "display_name": "Khadde",             # Human-readable name (for Sheets/Notion)
        "description": "Unique identifier for the plot"
    },
    {
        "name": "plot_name",
        "type": "text",
        "display_name": "Gairan",
        "description": "Plot name in Devanagari script (Marathi)"
    },
    {
        "name": "number_of_trees",
        "type": "number",
        "display_name": "Total Trees",
        "description": "Total count of trees in the plot"
    },
    {
        "name": "number_of_pits",
        "type": "number",
        "display_name": "Total Pits",
        "description": "Total count of pits in the plot"
    },
    {
        "name": "road_access_top_left",
        "type": "checkbox",
        "display_name": "Road Access",
        "description": "Checkbox indicator from top-left corner of document"
    },
    {
        "name": "photo_album_top_right",
        "type": "checkbox",
        "display_name": "Photo Album",
        "description": "Checkbox indicator from top-right corner of document"
    },
    {
        "name": "maps_bottom_left",
        "type": "checkbox",
        "display_name": "Location pin",
        "description": "Checkbox indicator from bottom-left corner of document"
    },
    {
        "name": "komoot_bottom_right",
        "type": "checkbox",
        "display_name": "Komoot",
        "description": "Checkbox indicator from bottom-right corner of document"
    },
]

"""
=============================================================================
HOW TO ADD A NEW FIELD:
=============================================================================

1. Add your field to Document AI custom extractor first
2. Add a new dictionary to the FIELDS list above with:
   - name: Must exactly match the field name in Document AI
   - type: Must be "text", "number", or "checkbox"
   - display_name: How it appears in Sheets/Notion
   - description: (optional) What this field represents

Example:
    {
        "name": "tree_species",
        "type": "text",
        "display_name": "Tree Species",
        "description": "Type of tree planted"
    },

3. The field will automatically appear in:
   - Google Sheets (as a new column)
   - Notion database (as a new property)
   - Document AI processing (will be extracted)

=============================================================================
HOW TO REMOVE A FIELD:
=============================================================================

Simply delete or comment out the entire dictionary block for that field.

=============================================================================
HOW TO REORDER FIELDS:
=============================================================================

Cut and paste the dictionary blocks in the order you want them to appear
in Sheets and Notion.

=============================================================================
"""
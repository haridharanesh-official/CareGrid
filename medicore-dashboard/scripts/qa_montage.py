from pathlib import Path

from PIL import Image, ImageDraw


root = Path(r"D:\CareGrid\medicore-dashboard")
pairs = [
    ("dashboard", "dashboard"),
    ("patients", "patients"),
    ("billing", "billing"),
    ("appointments", "appointments"),
]

for reference, implementation in pairs:
    source = Image.open(
        root / "reference-assets" / f"{reference}-reference.png"
    ).convert("RGB")
    rendered = Image.open(root / f"implementation-{implementation}.png").convert("RGB")
    rendered = rendered.resize(source.size)
    canvas = Image.new("RGB", (source.width * 2, source.height + 34), "white")
    canvas.paste(source, (0, 34))
    canvas.paste(rendered, (source.width, 34))
    labels = ImageDraw.Draw(canvas)
    labels.text((12, 10), "REFERENCE", fill="#17212f")
    labels.text((source.width + 12, 10), "IMPLEMENTATION", fill="#17212f")
    canvas.save(root / f"comparison-{reference}.png", quality=92)

# The supplied Inventory image includes a white presentation surround. Crop to
# the actual application frame before normalizing to the browser viewport.
inventory_source = Image.open(
    root / "reference-assets" / "inventory-reference-full.png"
).convert("RGB")
inventory_source = inventory_source.crop((150, 136, 1354, 992)).resize((1024, 724))
inventory_source.save(root / "reference-assets" / "inventory-reference.png")
inventory_rendered = Image.open(root / "implementation-inventory.png").convert("RGB")
inventory_rendered = inventory_rendered.resize((1024, 724))
inventory_canvas = Image.new("RGB", (2048, 758), "white")
inventory_canvas.paste(inventory_source, (0, 34))
inventory_canvas.paste(inventory_rendered, (1024, 34))
inventory_labels = ImageDraw.Draw(inventory_canvas)
inventory_labels.text((12, 10), "REFERENCE", fill="#17212f")
inventory_labels.text((1036, 10), "IMPLEMENTATION", fill="#17212f")
inventory_canvas.save(root / "comparison-inventory.png", quality=92)

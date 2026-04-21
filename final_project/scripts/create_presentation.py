from __future__ import annotations

import html
import zipfile
from pathlib import Path


OUT = Path(__file__).resolve().parents[1] / "Mini_Twitter_Cloud_Computing_Presentation.pptx"

SLIDE_W = 13_333_333
SLIDE_H = 7_500_000


def esc(text: str) -> str:
    return html.escape(text, quote=True)


def solid_fill(hex_color: str) -> str:
    return f'<a:solidFill><a:srgbClr val="{hex_color}"/></a:solidFill>'


def tx_body(lines: list[str], font_size: int = 2600, color: str = "1F2937", bold: bool = False) -> str:
    paragraphs = []
    for line in lines:
        if not line:
            paragraphs.append("<a:p/>")
            continue
        paragraphs.append(
            "<a:p>"
            f'<a:r><a:rPr lang="en-US" sz="{font_size}" b="{1 if bold else 0}">'
            f'{solid_fill(color)}'
            "</a:rPr>"
            f"<a:t>{esc(line)}</a:t></a:r>"
            "</a:p>"
        )
    return (
        "<p:txBody>"
        "<a:bodyPr wrap=\"square\"/>"
        "<a:lstStyle/>"
        + "".join(paragraphs)
        + "</p:txBody>"
    )


def textbox(idx: int, x: int, y: int, w: int, h: int, lines: list[str], size: int = 2600,
            color: str = "1F2937", bold: bool = False) -> str:
    return (
        f'<p:sp><p:nvSpPr><p:cNvPr id="{idx}" name="TextBox {idx}"/>'
        '<p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr>'
        '<p:spPr>'
        f'<a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{w}" cy="{h}"/></a:xfrm>'
        '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom>'
        '<a:noFill/><a:ln><a:noFill/></a:ln>'
        '</p:spPr>'
        + tx_body(lines, size, color, bold)
        + "</p:sp>"
    )


def rect(idx: int, x: int, y: int, w: int, h: int, text: str, fill: str = "EAF3FF",
         line: str = "2563EB", size: int = 2200, color: str = "111827", bold: bool = True) -> str:
    return (
        f'<p:sp><p:nvSpPr><p:cNvPr id="{idx}" name="Box {idx}"/>'
        '<p:cNvSpPr/><p:nvPr/></p:nvSpPr>'
        '<p:spPr>'
        f'<a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{w}" cy="{h}"/></a:xfrm>'
        '<a:prstGeom prst="roundRect"><a:avLst/></a:prstGeom>'
        f'{solid_fill(fill)}<a:ln w="18000"><a:solidFill><a:srgbClr val="{line}"/></a:solidFill></a:ln>'
        '</p:spPr>'
        '<p:txBody><a:bodyPr wrap="square" anchor="mid"/><a:lstStyle/>'
        '<a:p><a:pPr algn="ctr"/>'
        f'<a:r><a:rPr lang="en-US" sz="{size}" b="{1 if bold else 0}">{solid_fill(color)}</a:rPr>'
        f'<a:t>{esc(text)}</a:t></a:r></a:p></p:txBody>'
        '</p:sp>'
    )


def line_shape(idx: int, x1: int, y1: int, x2: int, y2: int, color: str = "64748B") -> str:
    x = min(x1, x2)
    y = min(y1, y2)
    w = abs(x2 - x1) or 1
    h = abs(y2 - y1) or 1
    flip_h = ' flipH="1"' if x2 < x1 else ""
    flip_v = ' flipV="1"' if y2 < y1 else ""
    return (
        f'<p:cxnSp><p:nvCxnSpPr><p:cNvPr id="{idx}" name="Connector {idx}"/>'
        '<p:cNvCxnSpPr/><p:nvPr/></p:nvCxnSpPr>'
        '<p:spPr>'
        f'<a:xfrm{flip_h}{flip_v}><a:off x="{x}" y="{y}"/><a:ext cx="{w}" cy="{h}"/></a:xfrm>'
        '<a:prstGeom prst="straightConnector1"><a:avLst/></a:prstGeom>'
        f'<a:ln w="28575"><a:solidFill><a:srgbClr val="{color}"/></a:solidFill>'
        '<a:tailEnd type="triangle"/></a:ln>'
        '</p:spPr></p:cxnSp>'
    )


def title_slide(title: str, subtitle: str) -> str:
    shapes = [
        textbox(2, 720000, 1600000, 11_800_000, 900000, [title], 4300, "0F172A", True),
        textbox(3, 730000, 2600000, 9_500_000, 500000, [subtitle], 2500, "2563EB", False),
        textbox(4, 730000, 3480000, 10_500_000, 1_500_000, [
            "FastAPI microservices | React frontend | AWS CDK",
            "ECS Fargate | RDS PostgreSQL | ElastiCache Redis | S3 | ALB",
        ], 2300, "374151", False),
        rect(5, 730000, 5550000, 2_300_000, 520000, "Cloud Computing", "EFF6FF", "2563EB", 1900),
        rect(6, 3_250_000, 5550000, 2_100_000, 520000, "Microservices", "ECFDF5", "059669", 1900),
        rect(7, 5_570_000, 5550000, 1_900_000, 520000, "Caching", "FFF7ED", "EA580C", 1900),
        rect(8, 7_690_000, 5550000, 2_100_000, 520000, "CDK Deploy", "F5F3FF", "7C3AED", 1900),
    ]
    return slide_xml(shapes)


def bullet_slide(title: str, bullets: list[str], accent: str = "2563EB") -> str:
    shapes = [
        textbox(2, 620000, 420000, 11_500_000, 500000, [title], 3300, "0F172A", True),
        rect(3, 620000, 1_080_000, 1_450_000, 105000, "", accent, accent, 100),
    ]
    y = 1_500_000
    for i, bullet in enumerate(bullets, start=4):
        shapes.append(rect(i * 2, 760000, y + 72000, 150000, 150000, "", accent, accent, 100))
        shapes.append(textbox(i * 2 + 1, 1_030_000, y, 11_100_000, 440000, [bullet], 2250, "1F2937", False))
        y += 570000
    return slide_xml(shapes)


def architecture_slide() -> str:
    shapes = [
        textbox(2, 620000, 420000, 11_500_000, 500000, ["High-Level Architecture"], 3300, "0F172A", True),
        rect(3, 620000, 1_080_000, 1_450_000, 105000, "", "2563EB", "2563EB", 100),
        rect(4, 4_700_000, 1_250_000, 3_900_000, 520000, "React Frontend on S3", "E0F2FE", "0284C7"),
        line_shape(5, 6_650_000, 1_770_000, 6_650_000, 2_210_000),
        rect(6, 4_700_000, 2_220_000, 3_900_000, 520000, "Application Load Balancer", "EEF2FF", "4F46E5"),
        line_shape(7, 6_650_000, 2_740_000, 6_650_000, 3_180_000),
        rect(8, 4_700_000, 3_190_000, 3_900_000, 520000, "Gateway Service :8080", "F5F3FF", "7C3AED"),
        line_shape(9, 6_650_000, 3_710_000, 3_100_000, 4_300_000),
        line_shape(10, 6_650_000, 3_710_000, 6_650_000, 4_300_000),
        line_shape(11, 6_650_000, 3_710_000, 10_200_000, 4_300_000),
        rect(12, 1_650_000, 4_320_000, 2_700_000, 520000, "User Service :8081", "ECFDF5", "059669"),
        rect(13, 5_300_000, 4_320_000, 2_700_000, 520000, "Tweet Service :8082", "FFF7ED", "EA580C"),
        rect(14, 8_950_000, 4_320_000, 2_900_000, 520000, "Timeline Service :8083", "FEF2F2", "DC2626"),
        line_shape(15, 3_000_000, 4_840_000, 5_250_000, 5_650_000),
        line_shape(16, 6_650_000, 4_840_000, 6_650_000, 5_650_000),
        line_shape(17, 10_400_000, 4_840_000, 8_050_000, 5_650_000),
        rect(18, 4_150_000, 5_680_000, 2_650_000, 520000, "RDS PostgreSQL", "F8FAFC", "475569"),
        rect(19, 7_030_000, 5_680_000, 2_150_000, 520000, "Redis Cache", "F8FAFC", "475569"),
        textbox(20, 780000, 6_650_000, 11_700_000, 420000, [
            "Public: S3 + ALB    Private: ECS services, RDS, Redis    Service discovery: AWS Cloud Map"
        ], 1850, "475569", False),
    ]
    return slide_xml(shapes)


def microservices_slide() -> str:
    shapes = [
        textbox(2, 620000, 420000, 11_500_000, 500000, ["Why Microservices?"], 3300, "0F172A", True),
        rect(3, 620000, 1_080_000, 1_450_000, 105000, "", "059669", "059669", 100),
        rect(4, 780000, 1_650_000, 2_650_000, 950000, "Gateway\nPublic API + routing", "F5F3FF", "7C3AED", 1950),
        rect(5, 3_850_000, 1_650_000, 2_650_000, 950000, "User\nAuth + follow graph", "ECFDF5", "059669", 1950),
        rect(6, 6_920_000, 1_650_000, 2_650_000, 950000, "Tweet\nPosts + likes + fan-out", "FFF7ED", "EA580C", 1950),
        rect(7, 9_990_000, 1_650_000, 2_650_000, 950000, "Timeline\nRead-optimized feeds", "FEF2F2", "DC2626", 1950),
        textbox(8, 920000, 3_280_000, 11_500_000, 2_700_000, [
            "• Clear responsibility boundaries",
            "• Independent container images and ECS services",
            "• Private service-to-service communication",
            "• Different services can scale based on workload",
            "• Architecture matches common cloud-native patterns",
        ], 2300, "1F2937"),
    ]
    return slide_xml(shapes)


def slide_xml(shapes: list[str]) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
        'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">'
        '<p:cSld><p:bg><p:bgPr><a:solidFill><a:srgbClr val="FFFFFF"/></a:solidFill>'
        '<a:effectLst/></p:bgPr></p:bg><p:spTree>'
        '<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>'
        '<p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/>'
        '<a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>'
        + "".join(shapes)
        + '</p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sld>'
    )


def presentation_xml(slide_count: int) -> str:
    sld_ids = "".join(
        f'<p:sldId id="{256 + i}" r:id="rId{i}"/>' for i in range(1, slide_count + 1)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<p:presentation xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
        'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">'
        '<p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rIdMaster"/></p:sldMasterIdLst>'
        f'<p:sldIdLst>{sld_ids}</p:sldIdLst>'
        f'<p:sldSz cx="{SLIDE_W}" cy="{SLIDE_H}" type="wide"/>'
        '<p:notesSz cx="6858000" cy="9144000"/>'
        '</p:presentation>'
    )


def presentation_rels(slide_count: int) -> str:
    rels = []
    for i in range(1, slide_count + 1):
        rels.append(
            f'<Relationship Id="rId{i}" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" '
            f'Target="slides/slide{i}.xml"/>'
        )
    rels.append(
        '<Relationship Id="rIdMaster" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" '
        'Target="slideMasters/slideMaster1.xml"/>'
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        + "".join(rels)
        + '</Relationships>'
    )


def content_types(slide_count: int) -> str:
    overrides = "".join(
        f'<Override PartName="/ppt/slides/slide{i}.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>'
        for i in range(1, slide_count + 1)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/ppt/presentation.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>'
        '<Override PartName="/ppt/slideMasters/slideMaster1.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml"/>'
        '<Override PartName="/ppt/slideLayouts/slideLayout1.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"/>'
        '<Override PartName="/ppt/theme/theme1.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>'
        '<Override PartName="/ppt/presProps.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.presentationml.presProps+xml"/>'
        '<Override PartName="/ppt/viewProps.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.presentationml.viewProps+xml"/>'
        '<Override PartName="/ppt/tableStyles.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.presentationml.tableStyles+xml"/>'
        '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
        '<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>'
        + overrides
        + '</Types>'
    )


def slide_rels() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" '
        'Target="../slideLayouts/slideLayout1.xml"/>'
        '</Relationships>'
    )


def slide_layout_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<p:sldLayout xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
        'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" type="blank" preserve="1">'
        '<p:cSld name="Blank"><p:spTree>'
        '<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>'
        '<p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/>'
        '<a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>'
        '</p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sldLayout>'
    )


def slide_layout_rels() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" '
        'Target="../slideMasters/slideMaster1.xml"/>'
        '</Relationships>'
    )


def slide_master_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<p:sldMaster xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
        'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">'
        '<p:cSld><p:bg><p:bgPr><a:solidFill><a:srgbClr val="FFFFFF"/></a:solidFill>'
        '<a:effectLst/></p:bgPr></p:bg><p:spTree>'
        '<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>'
        '<p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/>'
        '<a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>'
        '</p:spTree></p:cSld>'
        '<p:clrMap bg1="lt1" tx1="dk1" bg2="lt2" tx2="dk2" accent1="accent1" accent2="accent2" '
        'accent3="accent3" accent4="accent4" accent5="accent5" accent6="accent6" hlink="hlink" folHlink="folHlink"/>'
        '<p:sldLayoutIdLst><p:sldLayoutId id="2147483649" r:id="rId1"/></p:sldLayoutIdLst>'
        '<p:txStyles><p:titleStyle/><p:bodyStyle/><p:otherStyle/></p:txStyles>'
        '</p:sldMaster>'
    )


def slide_master_rels() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" '
        'Target="../slideLayouts/slideLayout1.xml"/>'
        '<Relationship Id="rId2" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" '
        'Target="../theme/theme1.xml"/>'
        '</Relationships>'
    )


def theme_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="Office">'
        '<a:themeElements><a:clrScheme name="Office">'
        '<a:dk1><a:srgbClr val="000000"/></a:dk1><a:lt1><a:srgbClr val="FFFFFF"/></a:lt1>'
        '<a:dk2><a:srgbClr val="1F2937"/></a:dk2><a:lt2><a:srgbClr val="F8FAFC"/></a:lt2>'
        '<a:accent1><a:srgbClr val="2563EB"/></a:accent1><a:accent2><a:srgbClr val="059669"/></a:accent2>'
        '<a:accent3><a:srgbClr val="EA580C"/></a:accent3><a:accent4><a:srgbClr val="7C3AED"/></a:accent4>'
        '<a:accent5><a:srgbClr val="DC2626"/></a:accent5><a:accent6><a:srgbClr val="0284C7"/></a:accent6>'
        '<a:hlink><a:srgbClr val="2563EB"/></a:hlink><a:folHlink><a:srgbClr val="7C3AED"/></a:folHlink>'
        '</a:clrScheme><a:fontScheme name="Office">'
        '<a:majorFont><a:latin typeface="Aptos Display"/><a:ea typeface=""/><a:cs typeface=""/></a:majorFont>'
        '<a:minorFont><a:latin typeface="Aptos"/><a:ea typeface=""/><a:cs typeface=""/></a:minorFont>'
        '</a:fontScheme><a:fmtScheme name="Office"><a:fillStyleLst><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:fillStyleLst>'
        '<a:lnStyleLst><a:ln w="9525"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln></a:lnStyleLst>'
        '<a:effectStyleLst><a:effectStyle><a:effectLst/></a:effectStyle></a:effectStyleLst>'
        '<a:bgFillStyleLst><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:bgFillStyleLst>'
        '</a:fmtScheme></a:themeElements></a:theme>'
    )


def pres_props() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<p:presentationPr xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
        'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"/>'
    )


def view_props() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<p:viewPr xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
        'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"/>'
    )


def table_styles() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<a:tblStyleLst xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" def="{5C22544A-7EE6-4342-B048-85BDC9FD1C3A}"/>'
    )


def root_rels() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="ppt/presentation.xml"/>'
        '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" '
        'Target="docProps/core.xml"/>'
        '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" '
        'Target="docProps/app.xml"/>'
        '</Relationships>'
    )


def core_props() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/" '
        'xmlns:dcterms="http://purl.org/dc/terms/" '
        'xmlns:dcmitype="http://purl.org/dc/dcmitype/" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
        '<dc:title>Distributed Mini Twitter on AWS</dc:title>'
        '<dc:creator>Codex</dc:creator>'
        '<cp:lastModifiedBy>Codex</cp:lastModifiedBy>'
        '<dcterms:created xsi:type="dcterms:W3CDTF">2026-04-20T00:00:00Z</dcterms:created>'
        '<dcterms:modified xsi:type="dcterms:W3CDTF">2026-04-20T00:00:00Z</dcterms:modified>'
        '</cp:coreProperties>'
    )


def app_props(slide_count: int) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" '
        'xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">'
        '<Application>Codex</Application>'
        f'<Slides>{slide_count}</Slides>'
        '</Properties>'
    )


def build_slides() -> list[str]:
    return [
        title_slide(
            "Distributed Mini Twitter on AWS",
            "Cloud Computing Final Project Presentation",
        ),
        bullet_slide("Project Goal", [
            "Build a cloud-native social media application",
            "Practice microservice decomposition and private service communication",
            "Optimize read-heavy timeline workloads with Redis",
            "Deploy containerized services using ECS Fargate",
            "Use AWS CDK for reproducible infrastructure",
            "Demonstrate the full system through a React frontend",
        ]),
        architecture_slide(),
        microservices_slide(),
        bullet_slide("Gateway Service", [
            "Single backend API entry point behind the ALB",
            "Routes /v1/* traffic to User, Tweet, and Timeline services",
            "Uses async reverse proxy behavior with httpx",
            "Applies Redis-backed per-IP rate limiting",
            "Keeps frontend configuration simple with one API base URL",
        ], "7C3AED"),
        bullet_slide("User Service", [
            "Handles registration, login, profiles, and JWT authentication",
            "Uses bcrypt password hashing",
            "Manages follow and unfollow relationships",
            "Maintains follower and following counts",
            "Invalidates Redis timeline cache after follow graph changes",
        ], "059669"),
        bullet_slide("Tweet Service", [
            "Creates and deletes tweets; handles likes and unlikes",
            "Writes durable tweet data to PostgreSQL",
            "Uses fan-out-on-write to push new tweet IDs into Redis timelines",
            "Supports strong or eventual consistency for like counts",
            "Provides batch tweet lookup for timeline enrichment",
        ], "EA580C"),
        bullet_slide("Timeline Service", [
            "Serves home timeline and user timeline endpoints",
            "Reads Redis timeline:{user_id} first for low-latency results",
            "Falls back to PostgreSQL when the cache misses",
            "Writes database fallback results back to Redis",
            "Calls Tweet Service batch endpoint to enrich timeline items",
        ], "DC2626"),
        bullet_slide("Data Layer", [
            "PostgreSQL stores durable state: users, tweets, follows, likes",
            "Redis stores cached timelines, pending like deltas, and rate limits",
            "PostgreSQL remains the source of truth",
            "Redis improves latency for repeated read-heavy workloads",
            "like_count_pending supports eventual like aggregation",
        ], "475569"),
        bullet_slide("AWS Infrastructure", [
            "Compute: ECS Fargate, 4 services, 0.25 vCPU and 512 MB each",
            "Database: RDS PostgreSQL 16 on t3.micro",
            "Cache: ElastiCache Redis 7 on cache.t3.micro",
            "Network: VPC across 2 AZs, public ALB, private services and databases",
            "Frontend: S3 static website hosting",
        ], "2563EB"),
        bullet_slide("CDK Stack Design", [
            "NetworkStack: VPC, public/private subnets, security groups",
            "DatabaseStack: RDS PostgreSQL, ElastiCache Redis, DB secret",
            "ContainerStack: ECS Fargate, ALB, Cloud Map, CloudWatch logs",
            "FrontendStack: S3 static website bucket and deployment",
            "CDK makes infrastructure reproducible and version-controlled",
        ], "7C3AED"),
        bullet_slide("Frontend", [
            "React + Vite application hosted on S3",
            "Auth flow: register, login, token persistence",
            "Main workflows: post tweet, read feed, like tweet",
            "User search supports follow and unfollow",
            "API wrapper reads the deployed ALB base URL",
        ], "0284C7"),
        bullet_slide("Code Review Plan", [
            "container_stack.py: ECS services, ALB rules, Cloud Map, env vars",
            "database_stack.py: RDS PostgreSQL and ElastiCache Redis",
            "network_stack.py: VPC, private/public subnets, security groups",
            "gateway/main.py: routing and rate limiting",
            "tweet/main.py and timeline/main.py: fan-out and Redis-first reads",
            "frontend/src/App.jsx: main user workflows",
        ], "0F766E"),
        bullet_slide("Deployment Demo Plan", [
            "Open the S3 frontend website",
            "Register or log in as a user",
            "Search for another user and follow them",
            "Post a tweet and open the home timeline",
            "Like a tweet and refresh to show persistence",
            "Optional: show ECS, ALB, RDS, Redis, and CloudWatch in AWS Console",
        ], "EA580C"),
        bullet_slide("Conclusion", [
            "Four containerized microservices deployed on ECS Fargate",
            "RDS PostgreSQL provides durable application state",
            "Redis improves timeline reads and supports rate limiting",
            "AWS CDK defines the cloud infrastructure as code",
            "The frontend demonstrates the end-to-end deployed system",
            "Future work: autoscaling, HTTPS, CI/CD, monitoring alarms",
        ], "2563EB"),
    ]


def main() -> None:
    slides = build_slides()
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types(len(slides)))
        z.writestr("_rels/.rels", root_rels())
        z.writestr("docProps/core.xml", core_props())
        z.writestr("docProps/app.xml", app_props(len(slides)))
        z.writestr("ppt/presentation.xml", presentation_xml(len(slides)))
        z.writestr("ppt/_rels/presentation.xml.rels", presentation_rels(len(slides)))
        z.writestr("ppt/slideMasters/slideMaster1.xml", slide_master_xml())
        z.writestr("ppt/slideMasters/_rels/slideMaster1.xml.rels", slide_master_rels())
        z.writestr("ppt/slideLayouts/slideLayout1.xml", slide_layout_xml())
        z.writestr("ppt/slideLayouts/_rels/slideLayout1.xml.rels", slide_layout_rels())
        z.writestr("ppt/theme/theme1.xml", theme_xml())
        z.writestr("ppt/presProps.xml", pres_props())
        z.writestr("ppt/viewProps.xml", view_props())
        z.writestr("ppt/tableStyles.xml", table_styles())
        for i, slide in enumerate(slides, start=1):
            z.writestr(f"ppt/slides/slide{i}.xml", slide)
            z.writestr(f"ppt/slides/_rels/slide{i}.xml.rels", slide_rels())
    print(OUT)


if __name__ == "__main__":
    main()

#target photoshop

/*
 * PARITY-003 Photoshop-side fixture oracle.
 *
 * Run this JSX from Photoshop's File > Scripts > Browse (or with the local
 * Photoshop -r launcher).  It creates only new 16x16 documents under the
 * caller-provided output directory; it never opens or writes the real PSD.
 * The resulting PNGs are reference candidates, not a promotion by themselves:
 * pair them with the exact Fusion host render and the PARITY-001 comparator.
 */
(function () {
    var outputRoot = $.getenv("PSD2FUSION_PARITY003_OUTPUT");
    if (!outputRoot || outputRoot === "") {
        outputRoot = "D:/Documents/PSD2Fusion/.local/parity003-fixtures/photoshop";
    }
    var root = new Folder(outputRoot);
    if (!root.exists) { root.create(); }
    var pngFolder = new Folder(outputRoot + "/reference");
    if (!pngFolder.exists) { pngFolder.create(); }
    var report = new File(outputRoot + "/oracle-result.txt");
    var oldUnits = app.preferences.rulerUnits;
    var oldDialogs = app.displayDialogs;
    var lines = [];
    function writeLine(value) { lines.push(String(value)); }
    function color(r, g, b) {
        var value = new SolidColor();
        value.rgb.red = r; value.rgb.green = g; value.rgb.blue = b;
        return value;
    }
    function fill(document, layer, value) {
        document.activeLayer = layer;
        document.selection.selectAll();
        document.selection.fill(value, ColorBlendMode.NORMAL, 100, false);
        document.selection.deselect();
    }
    function savePng(document, path) {
        var options = new PNGSaveOptions();
        options.interlaced = false;
        document.saveAs(new File(path), options, true, Extension.LOWERCASE);
    }
    function makeDocument(name) {
        return app.documents.add(16, 16, 72, name, NewDocumentMode.RGB, DocumentFill.TRANSPARENT);
    }
    function modeValue(name) {
        if (name === "Normal") { return BlendMode.NORMAL; }
        if (name === "Multiply") { return BlendMode.MULTIPLY; }
        if (name === "Linear Dodge") { return BlendMode.LINEARDODGE; }
        if (name === "Overlay") { return BlendMode.OVERLAY; }
        throw new Error("unsupported fixture mode: " + name);
    }
    function makeBlend(name) {
        var document = makeDocument("PARITY003-" + name);
        var backdrop = document.artLayers.add();
        backdrop.name = "Backdrop";
        fill(document, backdrop, color(46, 107, 194));
        backdrop.opacity = 50;
        var source = document.artLayers.add();
        source.name = "Source";
        fill(document, source, color(232, 56, 171));
        source.blendMode = modeValue(name);
        source.opacity = 50;
        savePng(document, pngFolder.fsName + "/" + name.replace(/ /g, "-").toLowerCase() + ".png");
        document.close(SaveOptions.DONOTSAVECHANGES);
    }
    function makeGroup() {
        var document = makeDocument("PARITY003-isolated-group");
        var backdrop = document.artLayers.add();
        backdrop.name = "Backdrop";
        fill(document, backdrop, color(31, 66, 148));
        backdrop.opacity = 50;
        var group = document.layerSets.add();
        group.name = "Isolated group";
        group.opacity = 50;
        var first = group.artLayers.add();
        first.name = "Group normal";
        fill(document, first, color(218, 46, 20));
        first.opacity = 75;
        var second = group.artLayers.add();
        second.name = "Group multiply";
        fill(document, second, color(56, 224, 92));
        second.blendMode = BlendMode.MULTIPLY;
        second.opacity = 75;
        savePng(document, pngFolder.fsName + "/isolated-group-opacity-050.png");
        document.close(SaveOptions.DONOTSAVECHANGES);
    }
    try {
        app.preferences.rulerUnits = Units.PIXELS;
        app.displayDialogs = DialogModes.NO;
        writeLine("status=PASS");
        writeLine("photoshop_version=" + app.version);
        writeLine("profile=sRGB IEC61966-2.1");
        makeBlend("Normal");
        makeBlend("Multiply");
        makeBlend("Linear Dodge");
        makeBlend("Overlay");
        makeGroup();
    } catch (error) {
        writeLine("status=FAIL");
        writeLine("error=" + error.toString());
    } finally {
        app.preferences.rulerUnits = oldUnits;
        app.displayDialogs = oldDialogs;
        try { report.open("w"); report.encoding = "UTF8"; report.write(lines.join("\n") + "\n"); report.close(); } catch (_) {}
    }
})();

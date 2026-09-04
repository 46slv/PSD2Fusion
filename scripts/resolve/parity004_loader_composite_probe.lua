-- Compare native Loader PostMultiply with explicit premultiplication through a
-- two-layer fractional-alpha/opacity composition in actual Fusion.
-- Usage: parity004_loader_composite_probe.lua <bottom.png> <top.png> <output-dir>

assert(arg and arg[1] and arg[2] and arg[3], "bottom, top, and output directory required")
local bottom_path, top_path, output_dir = arg[1], arg[2], arg[3]

local function text(value)
    if value == nil then return "nil" end
    return tostring(value)
end

local function exists(path)
    if bmd and bmd.fileexists and bmd.fileexists(path) then return true end
    local handle = io.open(path, "rb")
    if handle then handle:close() return true end
    return false
end

local function sequence(path)
    return string.sub(path, 1, -5) .. "0000.png"
end

local fusion = assert(bmd.scriptapp("Fusion", "localhost"), "Fusion endpoint unavailable")
local comp = assert(fusion:GetCurrentComp(), "no current Fusion composition")
local before = 0
for _, _ in pairs(comp:GetToolList(false) or {}) do before = before + 1 end

comp:Lock()
comp:StartUndo("PARITY-004 loader composite probe")
local ok, error_value = pcall(function()
    comp:SetAttrs({
        COMPN_GlobalStart = 0,
        COMPN_GlobalEnd = 0,
        COMPN_RenderStart = 0,
        COMPN_RenderEnd = 0,
    })

    local function loader(path, postmultiply, name, x, y)
        local tool = assert(comp:AddTool("Loader", x, y), "Loader add failed")
        tool:SetAttrs({TOOLS_Name = name})
        tool:SetInput("Clip", path)
        tool:SetInput("Clip1.PNGFormat.PostMultiply", postmultiply)
        tool:SetInput("GlobalIn", 0)
        tool:SetInput("GlobalOut", 1000)
        if postmultiply == 1 then return tool.Output end
        local multiply = assert(comp:AddTool("AlphaMultiply", x + 1, y), "AlphaMultiply add failed")
        multiply:SetAttrs({TOOLS_Name = name .. "_ExplicitPremult"})
        multiply:SetInput("Input", tool.Output)
        return multiply.Output
    end

    local function pipeline(postmultiply, label, y)
        local transparent = assert(comp:AddTool("Background", -6, y), "Background add failed")
        transparent:SetAttrs({TOOLS_Name = label .. "_Transparent"})
        transparent:SetInput("Width", 2)
        transparent:SetInput("Height", 2)
        transparent:SetInput("TopLeftRed", 0)
        transparent:SetInput("TopLeftGreen", 0)
        transparent:SetInput("TopLeftBlue", 0)
        transparent:SetInput("TopLeftAlpha", 0)
        local bottom = loader(bottom_path, postmultiply, label .. "_Bottom", -5, y - 1, y)
        local top = loader(top_path, postmultiply, label .. "_Top", -5, y + 1, y + 1)
        local base = assert(comp:AddTool("Merge", -2, y), "base Merge add failed")
        base:SetAttrs({TOOLS_Name = label .. "_Base"})
        base:SetInput("Background", transparent.Output)
        base:SetInput("Foreground", bottom)
        base:SetInput("ApplyMode", "Normal")
        base:SetInput("Blend", 1)
        base:SetInput("PerformDepthMerge", 0)
        local final = assert(comp:AddTool("Merge", 0, y), "final Merge add failed")
        final:SetAttrs({TOOLS_Name = label .. "_Final"})
        final:SetInput("Background", base.Output)
        final:SetInput("Foreground", top)
        final:SetInput("ApplyMode", "Normal")
        final:SetInput("Blend", 160 / 255)
        final:SetInput("PerformDepthMerge", 0)
        return final.Output
    end

    local native = pipeline(1, "Native", -2)
    local explicit = pipeline(0, "Explicit", 2)

    local function render(source, label, predivide)
        local requested = output_dir .. "\\" .. label .. ".png"
        pcall(function() os.remove(requested) end)
        pcall(function() os.remove(sequence(requested)) end)
        local saver = assert(comp:AddTool("Saver", 3, 0), "Saver add failed")
        saver:SetAttrs({TOOLS_Name = "P4LoaderCompositeSaver_" .. label})
        saver:SetInput("Clip", requested)
        saver:SetInput("PNGFormat.PreDivide", predivide)
        saver:SetInput("Input", source)
        local render_ok, render_value = pcall(function()
            return comp:Render({FrameRange = "0", Wait = true, Tool = saver})
        end)
        local found = nil
        for _ = 1, 12 do
            if exists(requested) then found = requested break end
            if exists(sequence(requested)) then found = sequence(requested) break end
            os.execute("ping -n 2 127.0.0.1 > nul")
        end
        print("RESULT=" .. label .. " OK=" .. text(render_ok)
            .. " VALUE=" .. text(render_value) .. " FOUND=" .. text(found))
    end

    local function straight_and_quantized(source, label, y)
        local straight = assert(comp:AddTool("AlphaDivide", 1, y), "AlphaDivide add failed")
        straight:SetAttrs({TOOLS_Name = label .. "_Straight"})
        straight:SetInput("Input", source)
        local quantized = assert(comp:AddTool("Custom", 2, y), "Custom add failed")
        quantized:SetAttrs({TOOLS_Name = label .. "_Quantized"})
        quantized:SetInput("Image1", straight.Output)
        quantized:SetInput("RedExpression", "floor(r1*255+0.5)/255")
        quantized:SetInput("GreenExpression", "floor(g1*255+0.5)/255")
        quantized:SetInput("BlueExpression", "floor(b1*255+0.5)/255")
        quantized:SetInput("AlphaExpression", "floor(a1*255+0.5)/255")
        render(source, label .. "-premult-predivide", 1)
        render(straight.Output, label .. "-straight-no-predivide", 0)
        render(quantized.Output, label .. "-quantized-no-predivide", 0)
    end

    straight_and_quantized(native, "native", -2)
    straight_and_quantized(explicit, "explicit", 2)
end)
if not ok then print("ERROR=" .. text(error_value)) end
pcall(function() comp:EndUndo(true) end)
pcall(function() comp:Undo() end)
pcall(function() comp:Unlock() end)
local after = 0
for _, _ in pairs(comp:GetToolList(false) or {}) do after = after + 1 end
print("RESTORED=" .. text(after == before))
print("DONE=true")

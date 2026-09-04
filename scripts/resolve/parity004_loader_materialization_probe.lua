-- Compare Fusion PNG-loader premultiplication with an explicit AlphaMultiply.
-- Usage: parity004_loader_materialization_probe.lua <asset.png> <output-dir>

assert(fusion, "Fusion scripting endpoint unavailable")
assert(arg and arg[1] and arg[2], "asset and output directory required")

local asset = arg[1]
local output_dir = arg[2]
local comp = assert(fusion:GetCurrentComp(), "no current Fusion composition")

local function text(value)
    if value == nil then return "nil" end
    return tostring(value)
end

local function sequence(path)
    return string.sub(path, 1, -5) .. "0000.png"
end

local function save(source, label, predivide)
    local path = output_dir .. "\\" .. label .. ".png"
    pcall(function() os.remove(path) end)
    pcall(function() os.remove(sequence(path)) end)
    local saver = assert(comp:AddTool("Saver", 2, 0), "Saver add failed")
    saver:SetAttrs({TOOLS_Name = "P4LoaderMaterializationSaver_" .. label})
    saver:SetInput("Clip", path)
    saver:SetInput("PNGFormat.PreDivide", predivide)
    saver:SetInput("Input", source)
    local ok, value = pcall(function()
        return comp:Render({FrameRange = "0", Wait = true, Tool = saver})
    end)
    local found = nil
    for _ = 1, 20 do
        if bmd.fileexists(path) then found = path break end
        if bmd.fileexists(sequence(path)) then found = sequence(path) break end
        os.execute("ping -n 2 127.0.0.1 > nul")
    end
    print("RESULT=" .. label .. " OK=" .. text(ok) .. " VALUE=" .. text(value)
        .. " FOUND=" .. text(found))
end

comp:Lock()
comp:StartUndo("PARITY-004 loader materialization probe")
local ok, error_value = pcall(function()
    comp:SetAttrs({
        COMPN_GlobalStart = 0,
        COMPN_GlobalEnd = 0,
        COMPN_RenderStart = 0,
        COMPN_RenderEnd = 0,
    })

    local native = assert(comp:AddTool("Loader", -4, 1), "native Loader add failed")
    native:SetAttrs({TOOLS_Name = "P4LoaderPostMultiply1"})
    native:SetInput("Clip", asset)
    native:SetInput("Clip1.PNGFormat.PostMultiply", 1)
    native:SetInput("GlobalIn", 0)
    native:SetInput("GlobalOut", 1000)

    local straight = assert(comp:AddTool("Loader", -4, -1), "straight Loader add failed")
    straight:SetAttrs({TOOLS_Name = "P4LoaderPostMultiply0"})
    straight:SetInput("Clip", asset)
    straight:SetInput("Clip1.PNGFormat.PostMultiply", 0)
    straight:SetInput("GlobalIn", 0)
    straight:SetInput("GlobalOut", 1000)
    local explicit = assert(comp:AddTool("AlphaMultiply", -2, -1), "AlphaMultiply add failed")
    explicit:SetAttrs({TOOLS_Name = "P4ExplicitAlphaMultiply"})
    explicit:SetInput("Input", straight.Output)
    local explicit_divide = assert(comp:AddTool("AlphaDivide", 0, -1), "AlphaDivide add failed")
    explicit_divide:SetAttrs({TOOLS_Name = "P4ExplicitAlphaDivide"})
    explicit_divide:SetInput("Input", explicit.Output)
    local custom = assert(comp:AddTool("Custom", -2, -3), "Custom add failed")
    custom:SetAttrs({TOOLS_Name = "P4CustomAlphaMultiply"})
    custom:SetInput("Image1", straight.Output)
    custom:SetInput("RedExpression", "r1*a1")
    custom:SetInput("GreenExpression", "g1*a1")
    custom:SetInput("BlueExpression", "b1*a1")
    custom:SetInput("AlphaExpression", "a1")
    local custom_divide = assert(comp:AddTool("AlphaDivide", 0, -3), "custom AlphaDivide add failed")
    custom_divide:SetAttrs({TOOLS_Name = "P4CustomAlphaDivide"})
    custom_divide:SetInput("Input", custom.Output)

    print("READBACK=native_postmultiply:" .. text(native:GetInput("Clip1.PNGFormat.PostMultiply"))
        .. " straight_postmultiply:" .. text(straight:GetInput("Clip1.PNGFormat.PostMultiply")))
    save(native.Output, "native-premult-predivide", 1)
    save(straight.Output, "straight-no-predivide", 0)
    save(straight.Output, "straight-with-predivide", 1)
    save(explicit.Output, "explicit-premult-predivide", 1)
    save(explicit.Output, "explicit-premult-no-predivide", 0)
    save(explicit_divide.Output, "explicit-roundtrip-no-predivide", 0)
    save(custom.Output, "custom-premult-predivide", 1)
    save(custom_divide.Output, "custom-roundtrip-no-predivide", 0)
end)
if not ok then print("ERROR=" .. text(error_value)) end
pcall(function() comp:EndUndo(true) end)
pcall(function() comp:Undo() end)
pcall(function() comp:Unlock() end)
print("DONE=true")

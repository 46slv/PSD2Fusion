-- Probe an explicit RGB8 output quantization boundary in actual Fusion.
--
-- Usage:
--   parity004_output_quantization_probe.lua <comp> <final-tool> <output-dir>
--
-- The probe pastes a generated comp into the disposable current composition,
-- renders the native premultiplied terminal, then renders the same terminal
-- through AlphaDivide -> Custom RGB8 bin-center encoding -> AlphaMultiply.
-- It is diagnostic only: the source composition is restored through Undo.

assert(arg and arg[1] and arg[2] and arg[3], "comp, final tool, and output directory required")
local comp_path = arg[1]
local final_name = arg[2]
local output_dir = arg[3]

local function text(value)
    if value == nil then return "nil" end
    local ok, result = pcall(function() return tostring(value) end)
    if ok then return result end
    return "<unprintable>"
end

local function exists(path)
    if bmd ~= nil and bmd.fileexists ~= nil then
        local ok, result = pcall(function() return bmd.fileexists(path) end)
        if ok and result then return true end
    end
    local handle = io.open(path, "rb")
    if handle == nil then return false end
    handle:close()
    return true
end

local function sequence(path)
    return string.sub(path, 1, -5) .. "0000.png"
end

local function find_tool(container, name)
    local list_ok, values = pcall(function() return container:GetToolList(false) end)
    if not list_ok or values == nil then values = {} end
    for _, tool in pairs(values) do
        local attrs = tool:GetAttrs() or {}
        if attrs.TOOLS_Name == name then return tool end
        if attrs.TOOLS_RegID == "GroupOperator" then
            local nested = find_tool(tool, name)
            if nested ~= nil then return nested end
        end
    end
    return nil
end

local function output_of(tool)
    local ok, value = pcall(function() return tool.Output end)
    if ok and value ~= nil then return value end
    ok, value = pcall(function() return tool.MainOutput1 end)
    if ok and value ~= nil then return value end
    return nil
end

local fusion = assert(bmd.scriptapp("Fusion", "localhost"), "Fusion endpoint unavailable")
local comp = assert(fusion:GetCurrentComp(), "no current Fusion composition")
local before = 0
for _, _ in pairs(comp:GetToolList(false) or {}) do before = before + 1 end

comp:Lock()
comp:StartUndo("PARITY-004 output quantization probe")
local ok, error_value = pcall(function()
    local settings = assert(bmd.readfile(comp_path), "composition read failed")
    assert(comp:Paste(settings) ~= false, "composition paste failed")
    comp:SetAttrs({
        COMPN_GlobalStart = 0,
        COMPN_GlobalEnd = 0,
        COMPN_RenderStart = 0,
        COMPN_RenderEnd = 0,
    })
    local final_tool = assert(find_tool(comp, final_name), "final tool not found: " .. final_name)
    local final_output = assert(output_of(final_tool), "final output unavailable")

    local straight = assert(comp:AddTool("AlphaDivide", -4, -2), "AlphaDivide add failed")
    straight:SetAttrs({TOOLS_Name = "P4OutputStraight"})
    straight:SetInput("Input", final_output)

    local quantized = assert(comp:AddTool("Custom", -2, -2), "Custom add failed")
    quantized:SetAttrs({TOOLS_Name = "P4OutputRGB8BinCenter"})
    quantized:SetInput("Image1", straight.Output)
    local function expression(channel)
        return "floor(" .. channel .. "1*255+0.5)/255"
    end
    quantized:SetInput("RedExpression", expression("r"))
    quantized:SetInput("GreenExpression", expression("g"))
    quantized:SetInput("BlueExpression", expression("b"))
    quantized:SetInput("AlphaExpression", expression("a"))

    local premult = assert(comp:AddTool("AlphaMultiply", 0, -2), "AlphaMultiply add failed")
    premult:SetAttrs({TOOLS_Name = "P4OutputRGB8Premult"})
    premult:SetInput("Input", quantized.Output)

    local function render(source, label, predivide)
        local requested = output_dir .. "\\" .. label .. ".png"
        pcall(function() os.remove(requested) end)
        pcall(function() os.remove(sequence(requested)) end)
        local saver = assert(comp:AddTool("Saver", 2, -2), "Saver add failed")
        saver:SetAttrs({TOOLS_Name = "P4OutputSaver_" .. label})
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

    render(final_output, "native-premult-predivide", 1)
    render(straight.Output, "native-straight-no-predivide", 0)
    render(quantized.Output, "quantized-straight-no-predivide", 0)
    render(premult.Output, "quantized-premult-predivide", 1)
    print("READBACK=red:" .. text(quantized:GetInput("RedExpression"))
        .. " alpha:" .. text(quantized:GetInput("AlphaExpression")))
end)
if not ok then print("ERROR=" .. text(error_value)) end
pcall(function() comp:EndUndo(true) end)
pcall(function() comp:Undo() end)
pcall(function() comp:Unlock() end)
local after = 0
for _, _ in pairs(comp:GetToolList(false) or {}) do after = after + 1 end
print("RESTORED=" .. text(after == before))
print("DONE=true")

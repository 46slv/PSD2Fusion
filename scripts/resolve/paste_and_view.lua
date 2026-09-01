-- Paste a generated tool set into the current composition and view its output.
local path = arg and arg[1]
assert(path and path ~= "", "usage: paste_and_view.lua <composition.comp>")

local fusion = bmd.scriptapp("Fusion", "localhost")
assert(fusion, "Fusion scripting endpoint is unavailable")
local comp = fusion:GetCurrentComp()
assert(comp, "No current Fusion composition")

local before = comp:GetToolList(false)
local before_objects = {}
local before_count = 0
for _, tool in pairs(before) do
    before_objects[tostring(tool)] = true
    before_count = before_count + 1
end

local settings = bmd.readfile(path)
assert(settings, "Unable to read generated composition")
local pasted = comp:Paste(settings)
assert(pasted ~= false, "Composition Paste failed")

local after = comp:GetToolList(false)
local after_count = 0
local added = {}
local media = nil
for _, tool in pairs(after) do
    after_count = after_count + 1
    if not before_objects[tostring(tool)] then
        table.insert(added, tool)
        local attrs = tool:GetAttrs()
        if attrs and attrs.TOOLS_RegID == "MediaOut" then
            media = tool
        end
    end
end

assert(after_count == before_count + #added, "Existing-tool identity/count check failed")
assert(media, "Pasted MediaOut was not found")

local output_tool = media
local connected = media.Input and media.Input:GetConnectedOutput()
if connected and connected.GetTool then
    output_tool = connected:GetTool() or media
end

local frame = comp.CurrentFrame
local flow = frame and frame.FlowView
if flow then
    flow:Select()
    flow:Select(output_tool)
end
comp:SetActiveTool(output_tool)

local output_attrs = output_tool:GetAttrs()
local output_name = output_attrs and output_attrs.TOOLS_Name or tostring(output_tool)

print("PASTE_PASS before=" .. tostring(before_count) .. " added=" .. tostring(#added) .. " after=" .. tostring(after_count))
print("EXISTING_TOOLS_PRESERVED=true")
print("OUTPUT_SELECTED=" .. tostring(output_name))

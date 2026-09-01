local name = arg and arg[1]
assert(name and name ~= "", "usage: select_tool.lua <tool-name>")
local fusion = bmd.scriptapp("Fusion", "localhost")
assert(fusion, "Fusion scripting endpoint is unavailable")
local comp = fusion:GetCurrentComp()
assert(comp, "No current Fusion composition")
comp.CurrentTime = 0
local tool = comp:FindTool(name)
assert(tool, "Tool was not found: " .. name)
local frame = comp.CurrentFrame
local flow = frame and frame.FlowView
if flow then
    flow:Select()
    flow:Select(tool)
end
comp:SetActiveTool(tool)
print("SELECT_PASS " .. name)

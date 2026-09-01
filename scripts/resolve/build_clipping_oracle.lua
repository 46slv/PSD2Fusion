-- Build a native-Fusion clipping micro-oracle in the current composition.
-- It intentionally uses Background/RectangleMask rather than Loader so the
-- viewer check is independent of still-image clip timing.
local fusion = bmd.scriptapp("Fusion", "localhost")
assert(fusion, "Fusion scripting endpoint is unavailable")
local comp = fusion:GetCurrentComp()
assert(comp, "No current Fusion composition")

local before = comp:GetToolList(false)
local before_count = 0
for _ in pairs(before) do before_count = before_count + 1 end

local function add(reg_id, name, x, y)
    local tool = comp:AddTool(reg_id, x, y)
    assert(tool, "Unable to create " .. reg_id)
    tool:SetAttrs({ TOOLS_Name = name })
    return tool
end

local function color(name, x, y, r, g, b, a)
    local tool = add("Background", name, x, y)
    tool:SetInput("Width", 480)
    tool:SetInput("Height", 320)
    tool:SetInput("TopLeftRed", r)
    tool:SetInput("TopLeftGreen", g)
    tool:SetInput("TopLeftBlue", b)
    tool:SetInput("TopLeftAlpha", a)
    return tool
end

local function merge(name, x, y, background, foreground, mode, blend, process_alpha, operator)
    local tool = add("Merge", name, x, y)
    tool.Background = background.Output
    tool.Foreground = foreground.Output
    tool:SetInput("ApplyMode", mode)
    tool:SetInput("Blend", blend)
    tool:SetInput("PerformDepthMerge", 0)
    if process_alpha ~= nil then tool:SetInput("ProcessAlpha", process_alpha and 1 or 0) end
    if operator ~= nil then tool:SetInput("Operator", operator) end
    return tool
end

comp:Lock()
comp:StartUndo("PSD2Fusion clipping micro-oracle")

local outer = color("OracleOuter", 0, 0, 0.18, 0.22, 0.30, 1.0)
local base = color("OracleBasePartialAlpha", 0, 2, 0.92, 0.16, 0.08, 0.58)
local base_mask = add("RectangleMask", "OracleBaseMatte", -1, 2)
base_mask:SetInput("Width", 0.64)
base_mask:SetInput("Height", 0.72)
base_mask:SetInput("SoftEdge", 0.08)
base.EffectMask = base_mask.Mask

local normal_member = color("OracleNormalMemberOpacity75", 2, 1, 0.08, 0.92, 0.25, 1.0)
local normal_mask = add("RectangleMask", "OracleNormalMemberMatte", 1, 1)
normal_mask:SetInput("Center", { 0.40, 0.50 })
normal_mask:SetInput("Width", 0.44)
normal_mask:SetInput("Height", 0.90)
normal_member.EffectMask = normal_mask.Mask

local multiply_member = color("OracleMultiplyMemberOpacity50", 2, 3, 0.15, 0.32, 0.95, 1.0)
local multiply_mask = add("RectangleMask", "OracleMultiplyMemberMatte", 1, 3)
multiply_mask:SetInput("Center", { 0.62, 0.50 })
multiply_mask:SetInput("Width", 0.42)
multiply_mask:SetInput("Height", 0.90)
multiply_member.EffectMask = multiply_mask.Mask

-- Both probes use the same fixed base matte and canonical member order.
local clip_normal = merge("OracleClipInNormal", 3, 1, base, normal_member, "Normal", 1.0, nil, "In")
local clip_multiply = merge("OracleClipInMultiply", 3, 3, base, multiply_member, "Normal", 1.0, nil, "In")

-- Former approximation: return to the outer stream after every member.
local old_base = merge("OracleOldBaseOuter", 4, 0, outer, base, "Normal", 1.0, nil, nil)
local old_normal = merge("OracleOldMemberOuter", 5, 0, old_base, clip_normal, "Normal", 0.75, nil, nil)
local old_result = merge("OracleOLD", 6, 0, old_normal, clip_multiply, "Multiply", 0.50, nil, nil)

-- Correct boundary: finish the clipping subtree while preserving base alpha,
-- then merge that completed result into the outer stream exactly once.
local stack_normal = merge("OracleNewStackNormal", 4, 3, base, clip_normal, "Normal", 0.75, false, nil)
local stack_multiply = merge("OracleNewStackMultiply", 5, 3, stack_normal, clip_multiply, "Multiply", 0.50, false, nil)
local new_result = merge("OracleNEW", 6, 3, outer, stack_multiply, "Normal", 1.0, nil, nil)

comp:EndUndo(true)
comp:Unlock()

local flow = comp.CurrentFrame and comp.CurrentFrame.FlowView
if flow then
    flow:Select()
    flow:Select(new_result)
end
comp:SetActiveTool(new_result)

local after_count = 0
for _ in pairs(comp:GetToolList(false)) do after_count = after_count + 1 end
print("ORACLE_BUILD_PASS before=" .. tostring(before_count) .. " added=" .. tostring(after_count - before_count) .. " after=" .. tostring(after_count))
print("OLD_OUTPUT=OracleOLD")
print("NEW_OUTPUT=OracleNEW")

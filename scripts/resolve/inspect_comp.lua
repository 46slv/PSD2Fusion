-- Non-destructive Resolve/Fusion graph and current-frame readback probe.
local path = arg and arg[1]
assert(path and path ~= "", "usage: inspect_comp.lua <composition.comp>")

local fusion = bmd.scriptapp("Fusion", "localhost")
assert(fusion, "Fusion scripting endpoint is unavailable")
local comp = fusion:LoadComp(path)
assert(comp, "Fusion failed to load composition")

local tools = comp:GetToolList(false)
local counts = {}
local total = 0
for _, tool in pairs(tools) do
    local attrs = tool:GetAttrs()
    local reg = attrs and attrs.TOOLS_RegID or "unknown"
    counts[reg] = (counts[reg] or 0) + 1
    total = total + 1
end

local media = comp:FindTool("MediaOut1")
assert(media, "MediaOut1 was not found")
local connected = media.Input and media.Input:GetConnectedOutput()
assert(connected, "MediaOut1 has no connected output")

print("LOAD_PASS tools=" .. tostring(total))
for key, value in pairs(counts) do
    print("COUNT " .. tostring(key) .. "=" .. tostring(value))
end
print("MEDIA_INPUT=" .. tostring(connected))

-- GetValue requests only the current output value. It is intentionally used
-- instead of Composition:Render, which is excluded by the project evidence.
local ok, frame = pcall(function() return connected:GetValue(comp.CurrentTime) end)
print("READBACK_CALL=" .. tostring(ok))
print("READBACK_VALUE=" .. tostring(frame))

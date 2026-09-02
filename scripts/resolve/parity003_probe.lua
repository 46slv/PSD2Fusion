-- Read-only PARITY-003 Fusion host probe.
--
-- Usage (from the Resolve installation directory):
--   fuscript.exe -l Lua -x "fusion=bmd.scriptapp('Fusion','localhost');fu=fusion" \
--     parity003_probe.lua <candidate.comp> [<candidate.comp> ...]
--
-- The probe loads each generated candidate, records graph controls and tries
-- one Saver render.  It never saves a Resolve project or the loaded
-- composition.  A render result is evidence only when the output file exists
-- and is compared by the PARITY-001 comparator; graph load alone is not proof.

local function text(value)
    if value == nil then return "nil" end
    local ok, result = pcall(function() return tostring(value) end)
    if ok then return result end
    return "<unprintable>"
end

local function safe_input(tool, name)
    local ok, value = pcall(function() return tool:GetInput(name) end)
    if ok then return value end
    return nil
end

assert(fusion, "Fusion scripting endpoint is unavailable")
assert(arg and #arg >= 1, "usage: parity003_probe.lua <candidate.comp> [...]")

print("HOST=Resolve/Fusion")
for index = 1, #arg do
    local path = arg[index]
    local record = {
        path = path,
        load = false,
        media = false,
        tools = 0,
        apply_modes = {},
        render_call = false,
        render_result = nil,
        render_output = nil,
    }
    local ok, comp_or_error = pcall(function() return fusion:LoadComp(path) end)
    if not ok or comp_or_error == nil then
        print("CANDIDATE=" .. text(path) .. " LOAD_PASS=false ERROR=" .. text(comp_or_error))
    else
        local comp = comp_or_error
        record.load = true
        local tools = comp:GetToolList(false)
        for _, tool in pairs(tools) do
            record.tools = record.tools + 1
            local attrs = tool:GetAttrs()
            local reg = attrs and attrs.TOOLS_RegID or "unknown"
            if reg == "Merge" then
                local mode = safe_input(tool, "ApplyMode")
                table.insert(record.apply_modes, text(mode))
            end
        end
        record.media = comp:FindTool("MediaOut1") ~= nil
        print("CANDIDATE=" .. text(path) .. " LOAD_PASS=true TOOLS=" .. text(record.tools) .. " MEDIA=" .. text(record.media))
        print("APPLY_MODES=" .. table.concat(record.apply_modes, "|"))

        -- Try a single frame Saver render in the loaded composition.  Resolve
        -- may reject this when no active project/timeline is open; that exact
        -- false result is retained as a blocker instead of being promoted.
        local connected = nil
        local media = comp:FindTool("MediaOut1")
        if media ~= nil and media.Input ~= nil then
            connected = media.Input:GetConnectedOutput()
        end
        if connected ~= nil then
            local saver_ok, saver = pcall(function() return comp:AddTool("Saver", 4, 0) end)
            if saver_ok and saver ~= nil then
                local output = path .. ".parity003-render.png"
                -- A prior run must not satisfy this run's output check.
                pcall(function() os.remove(output) end)
                pcall(function() saver:SetInput("Clip", output) end)
                pcall(function() saver:SetInput("Input", connected) end)
                -- Do not block the Resolve scripting endpoint: some Resolve
                -- project-manager states never finish a Saver render.  A
                -- bounded asynchronous call is enough to distinguish an
                -- accepted render request from the required output proof.
                local render_ok, render_result = pcall(function()
                    return comp:Render({FrameRange = "0", Wait = false, Tool = saver})
                end)
                record.render_call = render_ok
                record.render_result = render_result
                record.render_output = output
                local output_exists = false
                for _ = 1, 5 do
                    if bmd ~= nil and bmd.fileexists ~= nil then
                        local exists_ok, exists_result = pcall(function() return bmd.fileexists(output) end)
                        output_exists = exists_ok and exists_result == true
                    end
                    if output_exists then break end
                    os.execute("ping -n 2 127.0.0.1 > nul")
                end
                print("RENDER_CALL=" .. text(render_ok) .. " RESULT=" .. text(render_result) .. " OUTPUT=" .. text(output))
                print("RENDER_OUTPUT_EXISTS=" .. text(output_exists))
            else
                print("RENDER_CALL=false RESULT=Saver_add_failed")
            end
        else
            print("RENDER_CALL=false RESULT=MediaOut_not_connected")
        end
    end
end

vim.api.nvim_create_autocmd({ "BufRead", "BufNewFile" }, {
	pattern = { "*.tsx", "*.tmx", "*.xml" }, -- adjust patterns to your tiled map file extensions
	callback = function()
		-- force filetype xml for these files
		vim.bo.filetype = "xml"
	end,
})

-- .nvim.lua in your project root

-- Disable tsserver in this project
vim.api.nvim_create_autocmd("LspAttach", {
	callback = function(args)
		local client = vim.lsp.get_client_by_id(args.data.client_id)
		if client.name == "ts_ls" then
			print("❌ Disabling tsserver LSP for this project")
			client.stop()
		end
	end,
})

@{
    RootModule        = 'Tool.psm1'
    ModuleVersion     = '1.0.0'
    # RequiredModules = @('Commented.Module')
    RequiredModules   = @(
        'Az.Accounts',
        @{ModuleName = 'Microsoft.Graph.Authentication'; ModuleVersion = '2.0.0'},
        "PSDesiredStateConfiguration"  # note: bundled
    )
    FunctionsToExport = @('Get-Thing')
}

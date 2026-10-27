function Get-Widget {
    param($Name)
    Import-Module Example.Widgets
    . ./helpers.ps1
}
class Widget { }
enum Color { Red }
Get-Widget -Name x

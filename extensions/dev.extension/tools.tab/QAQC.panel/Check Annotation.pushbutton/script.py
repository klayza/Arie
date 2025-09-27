# -*- coding: utf-8 -*-
"""
Creates a simple WPF checklist window in the bottom-right corner of the screen.

FINAL CORRECTED VERSION: Uses script.invoke() to safely marshal UI commands
from the WPF thread to the main Revit API thread, which is the most robust
method for preventing crashes.
"""

# Imports
from pyrevit import forms, script
from pyrevit.framework import System

# 1. Helper function to be executed safely on the Revit main thread
def show_revit_alert(message, title):
    """
    This function contains the Revit API call. It will be passed to
    script.invoke() to ensure it runs on the correct thread.
    """
    forms.alert(message, title=title)


# 2. XAML Definition for the Window UI
xaml_string = r'''
<Window xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
        xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"
        Title="Checklist"
        SizeToContent="WidthAndHeight"
        WindowStyle="None"
        AllowsTransparency="True"
        Background="Transparent"
        Topmost="True"
        ShowInTaskbar="False">
    <Border Background="#2D2D30" CornerRadius="5" BorderBrush="#4A4A4A" BorderThickness="1" Padding="10">
        <StackPanel>
            <Button x:Name="checklist_item_1" Content="1. First Placeholder Item" Margin="5" Padding="8,5" Background="#3E3E42" Foreground="White" BorderThickness="0"/>
            <Button x:Name="checklist_item_2" Content="2. Second Placeholder Item" Margin="5" Padding="8,5" Background="#3E3E42" Foreground="White" BorderThickness="0"/>
            <Button x:Name="checklist_item_3" Content="3. Third Placeholder Item" Margin="5" Padding="8,5" Background="#3E3E42" Foreground="White" BorderThickness="0"/>
        </StackPanel>
    </Border>
</Window>
'''

# 3. WPF Window Class Definition
class ChecklistWindow(forms.WPFWindow):
    """
    A custom WPF Window that displays a checklist.
    It positions itself in the bottom-right corner of the screen upon loading.
    """
    def __init__(self):
        super(ChecklistWindow, self).__init__(xaml_string, literal_string=True)
        self.checklist_item_1.Click += self.item1_clicked
        self.checklist_item_2.Click += self.item2_clicked
        self.checklist_item_3.Click += self.item3_clicked
        self.Loaded += self.setup_window_position

    def setup_window_position(self, sender, args):
        """
        Calculates and sets the window position to the bottom-right corner
        of the primary screen's working area (respecting the taskbar).
        """
        working_area = System.Windows.Forms.Screen.PrimaryScreen.WorkingArea
        self.Left = working_area.Width - self.ActualWidth - 20
        self.Top = working_area.Height - self.ActualHeight - 20

    # Event Handlers for each checklist item
    def item1_clicked(self, sender, args):
        """Handles the click event by invoking the alert on the main thread."""
        script.invoke(
            show_revit_alert,
            "This is the placeholder message for item #1.",
            "Item 1 Clicked"
        )

    def item2_clicked(self, sender, args):
        """Handles the click event by invoking the alert on the main thread."""
        script.invoke(
            show_revit_alert,
            "Placeholder action for the second item has been triggered.",
            "Item 2 Clicked"
        )

    def item3_clicked(self, sender, args):
        """Handles the click event by invoking the alert on the main thread."""
        script.invoke(
            show_revit_alert,
            "You clicked the third and final placeholder item.",
            "Item 3 Clicked"
        )


# 4. Main Execution Block
if __name__ == '__main__':
    checklist_win = ChecklistWindow()
    checklist_win.show()
Output assets/demo.gif
Set FontSize 14
Set Width 1100
Set Height 660
Set Padding 18
Set Theme "Dracula"

Type "provena graph"
Sleep 40ms
Enter
Sleep 3500ms

Type "# rename the function whose signature the agent grounded a conclusion on"
Sleep 30ms
Enter
Sleep 800ms
Type "perl -pi -e 's/def parse_config/def parse_config_NEW/' provena/demo/source.py"
Sleep 30ms
Enter
Sleep 1000ms

Type "provena check"
Sleep 40ms
Enter
Sleep 3500ms

Type "git checkout provena/demo/source.py"
Sleep 30ms
Enter
Sleep 1500ms

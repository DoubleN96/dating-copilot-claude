#!/bin/bash
# ui.sh dump | tap "<texto>"  (Android emulado, $ANDROID_SERIAL)
A="adb -s ${ANDROID_SERIAL:-127.0.0.1:5556}"
$A shell uiautomator dump /sdcard/ui.xml >/dev/null 2>&1
X=$($A shell cat /sdcard/ui.xml)
if [ "$1" = dump ]; then echo "$X" | python3 -c "import sys,re; print([t for t in re.findall(r'(?:text|content-desc)=\"([^\"]+)\"',sys.stdin.read())][:30])"; exit; fi
B=$(echo "$X" | python3 -c "
import sys,re
x=sys.stdin.read(); w=sys.argv[1]
for m in re.finditer(r'<node [^>]*>',x):
    n=m.group(0)
    if 'text=\"'+w+'\"' in n or 'content-desc=\"'+w+'\"' in n:
        a=list(map(int,re.search(r'bounds=\"\[(\d+),(\d+)\]\[(\d+),(\d+)\]\"',n).groups())); print((a[0]+a[2])//2,(a[1]+a[3])//2); break" "$2")
[ -n "$B" ] && $A shell input tap $B && echo "tap '$2' @ $B" || echo "no encontrado: $2"

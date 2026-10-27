-- Dialogs must run in the applet itself: since macOS 26.5.2, background
-- processes (osascript spawned from python) can no longer take focus, so
-- their dialogs open hidden and the app appears to hang.

property langNames : {"English", "Spanish", "French", "German", "Italian", "Portuguese", "Chinese", "Japanese", "Korean", "Arabic", "Russian", "Hindi", "Dutch", "Turkish", "Polish", "Swedish", "Catalan"}
property supportedExtensions : {"mp3", "wav", "m4a", "flac", "ogg", "mp4", "webm", "aac", "wma"}
property runtimePath : ""
property launcherPath : ""
property shellPath : "export PATH=/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin; "

on run
	try
		my checkDependencies()
		activate
		set selectedFile to «event sysostdf» given «class prmp»:"Select an audio or video file to transcribe", «class ftyp»:supportedExtensions
		set theFile to my validateDroppedItems({selectedFile})
		my configureAndStart(theFile)
	on error errMsg number errNum
		my showError(errMsg, errNum)
	end try
end run

on open droppedItems
	try
		my checkDependencies()
		set theFile to my validateDroppedItems(droppedItems)
		my configureAndStart(theFile)
	on error errMsg number errNum
		my showError(errMsg, errNum)
	end try
end open

on checkDependencies()
	-- Setup writes this resource locally; no personal path is stored in source.
	set projectFile to POSIX path of (path to resource "project-path.txt")
	set projectPath to «event sysoexec» "/bin/cat " & quoted form of projectFile
	set runtimePath to projectPath & "/.venv/bin/python3"
	set launcherPath to projectPath & "/src/launch.py"
	«event sysoexec» shellPath & "if [ ! -x " & quoted form of runtimePath & " ]; then echo 'Python is missing. Run scripts/setup.sh in the Whisper project to repair the installation.' >&2; exit 1; fi; " & quoted form of runtimePath & " --version; if ! command -v ffmpeg >/dev/null 2>&1; then echo 'FFmpeg is missing. Run scripts/setup.sh in the Whisper project to repair the installation.' >&2; exit 1; fi; ffmpeg -version >/dev/null"
	«event sysoexec» quoted form of runtimePath & " -c " & quoted form of "import platform, sys; sys.exit(0 if platform.machine() == 'arm64' else 'Python must run natively on Apple Silicon. Run scripts/setup.sh to repair the installation.')"
end checkDependencies

on validateDroppedItems(droppedItems)
	if (count droppedItems) is not 1 then error "Drop or select one audio or video file at a time."

	set theFile to item 1 of droppedItems
	set audioPath to POSIX path of theFile
	set validationCommand to "audio_path=" & quoted form of audioPath & "; if [ ! -f \"$audio_path\" ]; then echo 'Please choose an audio or video file, not a folder.' >&2; exit 1; fi; extension=$(printf '%s' \"${audio_path##*.}\" | /usr/bin/tr '[:upper:]' '[:lower:]'); case \"$extension\" in mp3|wav|m4a|flac|ogg|mp4|webm|aac|wma) ;; *) echo 'This file type is not supported.' >&2; exit 1 ;; esac"
	«event sysoexec» validationCommand

	return theFile
end validateDroppedItems

on configureAndStart(theFile)
	set audioPath to POSIX path of theFile

	activate
	set langChoice to «event gtqpchlt» langNames given «class prmp»:"Select transcription language", «class inSL»:{"English"}, «class appr»:"Whisper Transcriber"
	if langChoice is false then return
	set langName to item 1 of langChoice

	activate
	set diarBtn to «class bhit» of («event sysodlog» "Enable speaker identification?" given «class appr»:"Speaker diarization", «class btns»:{"No", "Yes"}, «class dflt»:"No")
	set diarFlag to "no"
	if diarBtn is "Yes" then set diarFlag to "yes"

	-- The launcher hands the job to macOS and returns immediately, so closing
	-- Codex or Terminal cannot stop it. transcribe.py reads saved token settings.
	set launchCommand to shellPath & quoted form of runtimePath & " " & quoted form of launcherPath & " " & quoted form of audioPath & " " & quoted form of langName & " " & quoted form of diarFlag
	«event sysoexec» launchCommand
end configureAndStart

on showError(errMsg, errNum)
	if errNum is not -128 then
		activate
		«event sysodlog» errMsg given «class appr»:"Whisper Transcriber", «class btns»:{"OK"}, «class dflt»:"OK"
	end if
end showError

param([string]$Command, [string]$ArgumentsJsonBase64)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object Text.UTF8Encoding($false)
Add-Type -TypeDefinition @'
using System;
using System.Diagnostics;
using System.ComponentModel;
using System.Runtime.InteropServices;
using System.Text;
public static class BudgetJob {
  [StructLayout(LayoutKind.Sequential)] struct Basic {
    public long ProcessTime, JobTime; public uint Flags;
    public UIntPtr MinWorkingSet, MaxWorkingSet; public uint ActiveProcesses;
    public UIntPtr Affinity; public uint Priority, Scheduling;
  }
  [StructLayout(LayoutKind.Sequential)] struct Io {
    public ulong ReadOps, WriteOps, OtherOps, ReadBytes, WriteBytes, OtherBytes;
  }
  [StructLayout(LayoutKind.Sequential)] struct Extended {
    public Basic Limits; public Io Counters;
    public UIntPtr ProcessMemory, JobMemory, PeakProcessMemory, PeakJobMemory;
  }
  [DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true)] static extern IntPtr CreateJobObject(IntPtr attributes, string name);
  [DllImport("kernel32.dll", SetLastError=true)] static extern bool SetInformationJobObject(IntPtr job, int kind, ref Extended value, uint length);
  [DllImport("kernel32.dll", SetLastError=true)] static extern bool AssignProcessToJobObject(IntPtr job, IntPtr process);
  static IntPtr owner;
  static void Own() {
    owner=CreateJobObject(IntPtr.Zero,null);
    if(owner==IntPtr.Zero)throw new Win32Exception(Marshal.GetLastWin32Error());
    var limits=new Extended(); limits.Limits.Flags=0x2000; // KILL_ON_JOB_CLOSE
    if(!SetInformationJobObject(owner,9,ref limits,(uint)Marshal.SizeOf(typeof(Extended))) || !AssignProcessToJobObject(owner,Process.GetCurrentProcess().Handle))
      throw new Win32Exception(Marshal.GetLastWin32Error());
    // The job handle is non-inherited. It stays owned by this launcher until
    // process exit; the OS then terminates every remaining descendant.
  }
  public static string Quote(string value) {
    var result=new StringBuilder("\""); int slashes=0;
    foreach(char c in value) {
      if(c=='\\'){slashes++;continue;}
      if(c=='\"')result.Append('\\',slashes*2+1);
      else result.Append('\\',slashes);
      result.Append(c);slashes=0;
    }
    result.Append('\\',slashes*2);result.Append('"');return result.ToString();
  }
  public static int Run(string command,string arguments) {
    Own();
    var p=new Process();p.StartInfo=new ProcessStartInfo(command,arguments) {
      UseShellExecute=false,CreateNoWindow=true,RedirectStandardOutput=true,RedirectStandardError=true,
      StandardOutputEncoding=new UTF8Encoding(false),StandardErrorEncoding=new UTF8Encoding(false),
      WorkingDirectory=Environment.CurrentDirectory
    };
    p.OutputDataReceived+=(sender,e)=>{if(e.Data!=null)Console.Out.WriteLine(e.Data);};
    p.ErrorDataReceived+=(sender,e)=>{if(e.Data!=null)Console.Error.WriteLine(e.Data);};
    p.Start();p.BeginOutputReadLine();p.BeginErrorReadLine();p.WaitForExit();return p.ExitCode;
  }
}
'@
$arguments = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($ArgumentsJsonBase64)) | ConvertFrom-Json
$quoted = @($arguments | ForEach-Object { [BudgetJob]::Quote([string]$_) })
exit ([BudgetJob]::Run($Command, [string]::Join(' ', $quoted)))

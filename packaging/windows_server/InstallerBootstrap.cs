// A small .NET Framework bootstrapper for the manifest-verified Inno payload.
// The ZIP is stored after the PE image, so no individual resource exceeds 2 GB.
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Drawing;
using System.IO;
using System.IO.Compression;
using System.Linq;
using System.Reflection;
using System.Security.Cryptography;
using System.Text;
using System.Windows.Forms;

[assembly: AssemblyTitle("VietLip Server Setup")]
[assembly: AssemblyProduct("VietLip Server")]
[assembly: AssemblyVersion("1.10.1.0")]
[assembly: AssemblyFileVersion("1.10.1.0")]

internal sealed class PayloadFile {
    internal string Name, Hash;
    internal long Size;
    internal PayloadFile(string name, long size, string hash) { Name=name; Size=size; Hash=hash; }
}

internal sealed class SegmentStream : Stream {
    private readonly Stream source;
    private readonly long offset, length;
    private long position;
    internal SegmentStream(Stream source, long offset, long length) {
        this.source=source; this.offset=offset; this.length=length; source.Position=offset;
    }
    public override bool CanRead { get { return true; } }
    public override bool CanSeek { get { return true; } }
    public override bool CanWrite { get { return false; } }
    public override long Length { get { return length; } }
    public override long Position { get { return position; } set { Seek(value, SeekOrigin.Begin); } }
    public override int Read(byte[] buffer, int start, int count) {
        count=(int)Math.Min(count, length-position);
        source.Position=offset+position;
        int read=source.Read(buffer,start,count); position+=read; return read;
    }
    public override long Seek(long value, SeekOrigin origin) {
        long next=origin==SeekOrigin.Begin ? value : origin==SeekOrigin.Current ? position+value : length+value;
        if (next<0 || next>length) throw new IOException("Invalid payload seek.");
        position=next; return next;
    }
    public override void Flush() { }
    public override void SetLength(long value) { throw new NotSupportedException(); }
    public override void Write(byte[] buffer, int offset, int count) { throw new NotSupportedException(); }
}

internal static class Installer {
    private static readonly PayloadFile[] Files = new PayloadFile[] {
        /* PAYLOAD_FILES */
    };
    private static readonly string PayloadHash = "PAYLOAD_SHA256";
    private static readonly object LogLock = new object();
    internal static readonly string LogPath=Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
        "VietLip", "logs", "setup-"+DateTime.UtcNow.ToString("yyyyMMdd-HHmmss")+"-"+
        System.Diagnostics.Process.GetCurrentProcess().Id+".log");

    internal static void Log(string text) {
        lock(LogLock) {
            Directory.CreateDirectory(Path.GetDirectoryName(LogPath));
            File.AppendAllText(LogPath,DateTime.UtcNow.ToString("o")+" "+text+Environment.NewLine,Encoding.UTF8);
        }
    }
    private static string Hash(Stream input, Stream output, Func<bool> cancelled, Action<long> progress) {
        byte[] buffer=new byte[1024*1024]; long total=0;
        using(var hash=SHA256.Create()) {
            int read;
            while((read=input.Read(buffer,0,buffer.Length))>0) {
                if(cancelled()) throw new OperationCanceledException();
                if(output!=null) output.Write(buffer,0,read);
                hash.TransformBlock(buffer,0,read,buffer,0); total+=read; progress(total);
            }
            hash.TransformFinalBlock(new byte[0],0,0);
            return BitConverter.ToString(hash.Hash).Replace("-","").ToLowerInvariant();
        }
    }
    private static string Quote(string arg) {
        var result=new StringBuilder("\""); int slashes=0;
        foreach(char c in arg) {
            if(c=='\\') { slashes++; continue; }
            result.Append('\\', c=='"' ? slashes*2+1 : slashes); result.Append(c); slashes=0;
        }
        result.Append('\\',slashes*2); return result.Append('"').ToString();
    }
    internal static int Run(string[] args, Func<bool> cancelled, Action<int,string> progress) {
        bool verify=args.Any(a=>a.Equals("--verify",StringComparison.OrdinalIgnoreCase));
        string tempRoot=Path.GetFullPath(Path.GetTempPath()).TrimEnd(Path.DirectorySeparatorChar)+Path.DirectorySeparatorChar;
        string work=Path.Combine(tempRoot,"VietLip-setup-"+Guid.NewGuid().ToString("N"));
        bool created=false;
        try {
            Log(verify ? "Verify-only started." : "Installer preparation started.");
            using(var file=File.OpenRead(Assembly.GetExecutingAssembly().Location)) {
                if(file.Length<56) throw new InvalidDataException("Bộ cài chưa đầy đủ.");
                file.Seek(-56,SeekOrigin.End);
                var reader=new BinaryReader(file,Encoding.UTF8,true);
                if(Encoding.ASCII.GetString(reader.ReadBytes(8))!="VTLIP101") throw new InvalidDataException("Sai định dạng bộ cài.");
                long offset=reader.ReadInt64(), length=reader.ReadInt64();
                string recordedHash=BitConverter.ToString(reader.ReadBytes(32)).Replace("-","").ToLowerInvariant();
                if(offset<4096 || length<=0 || offset>file.Length-56 || length!=file.Length-56-offset || recordedHash!=PayloadHash)
                    throw new InvalidDataException("Bộ cài bị thiếu hoặc đã thay đổi.");
                using(var payload=new SegmentStream(file,offset,length)) {
                    string actual=Hash(payload,null,cancelled,n=>progress((int)(n*20/length),"Kiểm tra bộ cài…"));
                    if(actual!=PayloadHash) throw new InvalidDataException("Kiểm tra SHA-256 thất bại. Hãy lấy lại bộ cài.");
                    payload.Position=0;
                    using(var zip=new ZipArchive(payload,ZipArchiveMode.Read,true)) {
                        if(zip.Entries.Count!=Files.Length || zip.Entries.Select(e=>e.FullName).Distinct(StringComparer.Ordinal).Count()!=Files.Length)
                            throw new InvalidDataException("Danh sách file trong bộ cài không hợp lệ.");
                        long total=Files.Sum(f=>f.Size), completed=0;
                        if(!verify) {
                            if(new DriveInfo(Path.GetPathRoot(tempRoot)).AvailableFreeSpace<total+268435456)
                                throw new IOException("Cần khoảng 3,5 GB trống ở ổ chứa thư mục tạm để mở bộ cài.");
                            Directory.CreateDirectory(work); created=true; Log("Temporary payload: "+work);
                        }
                        foreach(var expected in Files) {
                            var entry=zip.GetEntry(expected.Name);
                            // Exact allowlist: no archive-supplied path is used for extraction.
                            if(entry==null || entry.Length!=expected.Size || Path.GetFileName(expected.Name)!=expected.Name)
                                throw new InvalidDataException("File cài đặt không hợp lệ: "+expected.Name);
                            string hash;
                            using(var input=entry.Open()) {
                                using(var output=verify ? null : new FileStream(Path.Combine(work,expected.Name),FileMode.CreateNew,FileAccess.Write,FileShare.None)) {
                                    hash=Hash(input,output,cancelled,n=>progress(20+(int)((completed+n)*75/total),verify ? "Kiểm tra dữ liệu…" : "Chuẩn bị cài VietLip Server…"));
                                }
                            }
                            if(hash!=expected.Hash) throw new InvalidDataException("Sai SHA-256: "+expected.Name);
                            completed+=expected.Size; Log("Verified: "+expected.Name);
                        }
                    }
                }
            }
            if(verify) { Log("Verification passed."); return 0; }
            if(cancelled()) throw new OperationCanceledException();
            progress(100,"install");
            string setup=Path.Combine(work,Files.Single(f=>f.Name.EndsWith(".exe",StringComparison.OrdinalIgnoreCase)).Name);
            var start=new System.Diagnostics.ProcessStartInfo(setup,String.Join(" ",args.Select(Quote))) {
                WorkingDirectory=work, UseShellExecute=false
            };
            using(var process=System.Diagnostics.Process.Start(start)) {
                process.WaitForExit(); Log("Inno Setup exit: "+process.ExitCode); return process.ExitCode;
            }
        } finally {
            if(created) {
                string resolved=Path.GetFullPath(work);
                if(!resolved.StartsWith(tempRoot,StringComparison.OrdinalIgnoreCase) ||
                   Path.GetFileName(resolved).Length!="VietLip-setup-".Length+32 ||
                   !Path.GetFileName(resolved).StartsWith("VietLip-setup-",StringComparison.Ordinal))
                    throw new InvalidOperationException("Unsafe temporary cleanup path.");
                try { Directory.Delete(resolved,true); Log("Temporary payload removed."); }
                catch(Exception error) { Log("Temporary cleanup pending: "+error.Message); }
            }
        }
    }
}

internal sealed class PrepareForm : Form {
    private readonly BackgroundWorker worker=new BackgroundWorker();
    private readonly Label status=new Label();
    private readonly ProgressBar bar=new ProgressBar();
    private readonly Button cancel=new Button();
    private bool done;
    internal int ExitCode=1;
    internal PrepareForm(string[] args) {
        Text="VietLip Server"; ClientSize=new Size(480,188); BackColor=Color.White;
        FormBorderStyle=FormBorderStyle.FixedDialog; MaximizeBox=false; MinimizeBox=false;
        StartPosition=FormStartPosition.CenterScreen; Font=new Font("Segoe UI",10);
        Icon=Icon.ExtractAssociatedIcon(Assembly.GetExecutingAssembly().Location);
        var title=new Label { Text="VietLip Server",Font=new Font("Segoe UI",18,FontStyle.Bold),AutoSize=true,Location=new Point(24,18) };
        status.Text="Chuẩn bị bộ cài…"; status.Location=new Point(26,65); status.Size=new Size(430,28);
        bar.Location=new Point(28,104); bar.Size=new Size(424,8);
        cancel.Text="Hủy"; cancel.Location=new Point(350,137); cancel.Size=new Size(100,30);
        Controls.AddRange(new Control[]{title,status,bar,cancel});
        worker.WorkerSupportsCancellation=true; worker.WorkerReportsProgress=true;
        int lastProgress=-1;
        worker.DoWork+=(sender,eventArgs)=> {
            eventArgs.Result=Installer.Run(args,()=>worker.CancellationPending,(percent,message)=> {
                if(percent!=lastProgress || message=="install") { lastProgress=percent; worker.ReportProgress(percent,message); }
            });
        };
        worker.ProgressChanged+=(sender,eventArgs)=> {
            string message=(string)eventArgs.UserState;
            if(message=="install") { cancel.Enabled=false; Hide(); }
            else { bar.Value=Math.Max(0,Math.Min(100,eventArgs.ProgressPercentage)); status.Text=message; }
        };
        worker.RunWorkerCompleted+=(sender,eventArgs)=> {
            done=true;
            if(eventArgs.Error!=null) {
                Installer.Log(eventArgs.Error.ToString()); ExitCode=2;
                if(!(eventArgs.Error is OperationCanceledException))
                    MessageBox.Show(eventArgs.Error.Message+"\n\nNhật ký: "+Installer.LogPath,"VietLip Server",MessageBoxButtons.OK,MessageBoxIcon.Error);
            } else ExitCode=(int)eventArgs.Result;
            Close();
        };
        cancel.Click+=(sender,eventArgs)=> { worker.CancelAsync(); cancel.Enabled=false; status.Text="Đang hủy…"; };
        FormClosing+=(sender,eventArgs)=> { if(!done) { worker.CancelAsync(); eventArgs.Cancel=true; } };
        Shown+=(sender,eventArgs)=>worker.RunWorkerAsync();
    }
}

internal static class Program {
    [STAThread]
    private static int Main(string[] args) {
        bool quiet=args.Any(a=>a.Equals("/VERYSILENT",StringComparison.OrdinalIgnoreCase) || a.Equals("/SILENT",StringComparison.OrdinalIgnoreCase) || a.Equals("--verify",StringComparison.OrdinalIgnoreCase));
        if(quiet) {
            try { return Installer.Run(args,()=>false,(percent,message)=>{}); }
            catch(Exception error) { Installer.Log(error.ToString()); return 2; }
        }
        Application.EnableVisualStyles(); Application.SetCompatibleTextRenderingDefault(false);
        using(var form=new PrepareForm(args)) { Application.Run(form); return form.ExitCode; }
    }
}

import os
import queue
import threading
import zipfile
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageOps

APP_TITLE = "AKASH TECH SOLUTIONS - Project Bulk Image Processing"
SUPPORTED = {".jpg", ".jpeg", ".png", ".webp"}
MAX_FILE_MB = 50

GREEN = "#08783F"
GREEN_DARK = "#075A30"
GREEN_LIGHT = "#EAF7EF"
GREEN_PALE = "#F4FBF6"
BLACK = "#0B1711"
TEXT = "#17221C"
MUTED = "#66736B"
BORDER = "#D5E2D9"
WHITE = "#FFFFFF"
RED = "#C62828"


class CompletionDialog(tk.Toplevel):
    def __init__(self, parent, processed, failed, input_mb, output_mb, output_path):
        super().__init__(parent)
        self.title("Processing Complete")
        self.geometry("500x330")
        self.resizable(False, False)
        self.configure(bg=WHITE)
        self.transient(parent)
        self.grab_set()

        header = tk.Frame(self, bg=GREEN_DARK, height=66)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="✓", bg=GREEN_DARK, fg=WHITE,
                 font=("Segoe UI", 22, "bold")).pack(side="left", padx=22)
        tk.Label(header, text="Processing Complete", bg=GREEN_DARK, fg=WHITE,
                 font=("Segoe UI", 15, "bold")).pack(side="left")

        body = tk.Frame(self, bg=WHITE)
        body.pack(fill="both", expand=True, padx=28, pady=20)

        tk.Label(body, text="The image batch has been processed successfully.",
                 bg=WHITE, fg=TEXT, font=("Segoe UI", 10)).pack(anchor="w")

        stats = tk.Frame(body, bg=GREEN_PALE, highlightbackground=BORDER, highlightthickness=1)
        stats.pack(fill="x", pady=16)
        for label, value in [
            ("Processed", processed),
            ("Failed", failed),
            ("Input", f"{input_mb:.2f} MB"),
            ("Output", f"{output_mb:.2f} MB"),
        ]:
            cell = tk.Frame(stats, bg=GREEN_PALE)
            cell.pack(side="left", expand=True, fill="x", padx=8, pady=12)
            tk.Label(cell, text=str(value), bg=GREEN_PALE, fg=GREEN_DARK,
                     font=("Segoe UI", 14, "bold")).pack()
            tk.Label(cell, text=label, bg=GREEN_PALE, fg=MUTED,
                     font=("Segoe UI", 8)).pack()

        tk.Label(body, text="Output location", bg=WHITE, fg=MUTED,
                 font=("Segoe UI", 8, "bold")).pack(anchor="w")
        tk.Label(body, text=str(output_path), bg=WHITE, fg=TEXT,
                 font=("Segoe UI", 9), wraplength=430, justify="left").pack(anchor="w", pady=(2, 10))

        btns = tk.Frame(body, bg=WHITE)
        btns.pack(fill="x", side="bottom")
        tk.Button(btns, text="Open Output Folder", command=lambda: (parent.open_output(), self.destroy()),
                  bg=GREEN, fg=WHITE, activebackground=GREEN_DARK, activeforeground=WHITE,
                  relief="flat", bd=0, padx=18, pady=9, font=("Segoe UI", 9, "bold")).pack(side="left")
        tk.Button(btns, text="Close", command=self.destroy,
                  bg="#EEF2EF", fg=TEXT, activebackground="#DCE7E0",
                  relief="flat", bd=0, padx=18, pady=9, font=("Segoe UI", 9, "bold")).pack(side="right")


class BulkImageProcessor(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.state("zoomed")
        self.minsize(1100, 720)
        self.configure(bg=GREEN_PALE)

        self.files = []
        self.results = []
        self.msg_queue = queue.Queue()
        self.processing = False

        self._setup_style()
        self._build_ui()
        self.after(100, self._poll_queue)
        self._status("Ready | Add images or select a folder to begin")

    def _setup_style(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("Treeview", rowheight=36, font=("Segoe UI", 9),
                        background=WHITE, fieldbackground=WHITE, foreground=TEXT,
                        borderwidth=0)
        style.configure("Treeview.Heading", background=GREEN_DARK, foreground=WHITE,
                        font=("Segoe UI", 9, "bold"), padding=9)
        style.map("Treeview", background=[("selected", "#D9F1E2")],
                  foreground=[("selected", TEXT)])
        style.configure("TCombobox", padding=7, font=("Segoe UI", 9))
        style.configure("TEntry", padding=7)
        style.configure("Horizontal.TProgressbar", troughcolor="#DCE9E0",
                        background=GREEN, bordercolor="#DCE9E0",
                        lightcolor=GREEN, darkcolor=GREEN)

    def _build_ui(self):
        self._build_header()

        main = tk.Frame(self, bg=GREEN_PALE)
        main.pack(fill="both", expand=True, padx=18, pady=16)

        self._build_toolbar(main)

        content = tk.Frame(main, bg=GREEN_PALE, height=396)
        content.pack(fill="x", pady=(10, 0))
        content.pack_propagate(False)

        left = tk.Frame(content, bg=WHITE, highlightbackground=BORDER, highlightthickness=1)
        left.pack(side="left", fill="both", expand=True, padx=(0, 8))

        right = tk.Frame(content, bg=WHITE, highlightbackground=BORDER, highlightthickness=1, width=435)
        right.pack(side="right", fill="y", padx=(8, 0))
        right.pack_propagate(False)

        self._build_queue(left)
        self._build_options(right)

        bottom = tk.Frame(main, bg=GREEN_PALE, height=112)
        bottom.pack(fill="x", pady=(10, 0))
        bottom.pack_propagate(False)
        self._build_progress(bottom)
        self._build_summary(bottom)

        self.status = tk.Label(self, bg=GREEN_DARK, fg=WHITE, anchor="w",
                               padx=18, font=("Segoe UI", 8, "bold"), height=2)
        self.status.pack(fill="x", side="bottom")

    def _build_header(self):
        header = tk.Frame(self, bg=BLACK, height=96)
        header.pack(fill="x")
        header.pack_propagate(False)

        logo = tk.Canvas(header, width=66, height=66, bg=BLACK, highlightthickness=0)
        logo.pack(side="left", padx=(22, 12), pady=15)
        logo.create_polygon(33, 5, 59, 57, 45, 57, 38, 43, 28, 43, 21, 57, 7, 57,
                            fill="#00B85A", outline="")
        logo.create_polygon(31, 18, 22, 40, 40, 40, fill="#8EF0B8", outline="")

        title = tk.Frame(header, bg=BLACK)
        title.pack(side="left", fill="y", pady=13)
        tk.Label(title, text="AKASH", bg=BLACK, fg=WHITE,
                 font=("Segoe UI", 22, "bold")).pack(anchor="w")
        tk.Label(title, text="TECH SOLUTIONS", bg=BLACK, fg="#9CE8BB",
                 font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(0, 2))

        tk.Frame(header, bg="#435249", width=1).pack(side="left", fill="y", pady=18, padx=22)

        project = tk.Frame(header, bg=BLACK)
        project.pack(side="left", pady=18)
        tk.Label(project, text="Project - Bulk Image Processing", bg=BLACK, fg=WHITE,
                 font=("Segoe UI", 18, "bold")).pack(anchor="w")
        tk.Label(project, text="RESIZE   |   CONVERT   |   RENAME   |   OPTIMIZE   |   BATCH PROCESSING",
                 bg=BLACK, fg="#B6C6BC", font=("Segoe UI", 7, "bold")).pack(anchor="w", pady=(4,0))

        actions = tk.Frame(header, bg=BLACK)
        actions.pack(side="right", padx=22)
        self._header_button(actions, "⚙", "Settings", self.show_settings).pack(side="left", padx=4)
        self._header_button(actions, "?", "Help", self.show_help).pack(side="left", padx=4)
        self._header_button(actions, "i", "About", self.show_about).pack(side="left", padx=4)

    def _header_button(self, parent, symbol, text, command):
        f = tk.Frame(parent, bg="#102019", highlightbackground="#284337", highlightthickness=1)
        tk.Button(f, text=symbol, command=command, bg="#102019", fg=WHITE,
                  activebackground=GREEN, activeforeground=WHITE, relief="flat", bd=0,
                  font=("Segoe UI", 13, "bold"), width=4).pack()
        tk.Label(f, text=text, bg="#102019", fg="#D8E7DE",
                 font=("Segoe UI", 7, "bold")).pack(padx=5, pady=(0,5))
        return f

    def _button(self, parent, text, command, primary=False, width=None):
        return tk.Button(parent, text=text, command=command,
                         bg=GREEN if primary else WHITE,
                         fg=WHITE if primary else TEXT,
                         activebackground=GREEN_DARK if primary else "#E8F2EB",
                         activeforeground=WHITE if primary else TEXT,
                         relief="flat", bd=0, padx=15, pady=9,
                         font=("Segoe UI", 9, "bold"), width=width or 0,
                         cursor="hand2")

    def _build_toolbar(self, parent):
        bar = tk.Frame(parent, bg=GREEN_PALE)
        bar.pack(fill="x")
        self._button(bar, "▣  Add Images", self.add_images, True).pack(side="left", padx=(0,7))
        self._button(bar, "▰  Add Folder", self.add_folder, True).pack(side="left", padx=7)
        self._button(bar, "−  Remove Selected", self.remove_selected).pack(side="left", padx=7)
        self._button(bar, "✕  Clear List", self.clear_list).pack(side="left", padx=7)

        self.count_label = tk.Label(bar, text="Total Files: 0", bg=GREEN_PALE, fg=TEXT,
                                    font=("Segoe UI", 10, "bold"))
        self.count_label.pack(side="right", padx=10)

    def _section_title(self, parent, title, subtitle=None):
        head = tk.Frame(parent, bg=GREEN_LIGHT, height=48)
        head.pack(fill="x")
        head.pack_propagate(False)
        tk.Label(head, text=title, bg=GREEN_LIGHT, fg=GREEN_DARK,
                 font=("Segoe UI", 10, "bold")).pack(side="left", padx=15, pady=14)
        if subtitle:
            tk.Label(head, text=subtitle, bg=GREEN_LIGHT, fg=MUTED,
                     font=("Segoe UI", 8)).pack(side="right", padx=15)
        return head

    def _build_queue(self, parent):
        self._section_title(parent, "IMAGE QUEUE", "JPG • PNG • WEBP")
        table = tk.Frame(parent, bg=WHITE)
        table.pack(fill="both", expand=True, padx=10, pady=10)
        cols = ("file","format","dimensions","size","status","output")
        self.tree = ttk.Treeview(table, columns=cols, show="headings", selectmode="extended")
        heads = {"file":"File Name","format":"Format","dimensions":"Original Size (px)",
                 "size":"File Size","status":"Status","output":"Output Name"}
        widths = {"file":270,"format":80,"dimensions":145,"size":95,"status":115,"output":170}
        for c in cols:
            self.tree.heading(c,text=heads[c])
            self.tree.column(c,width=widths[c],anchor="w")
        sy = ttk.Scrollbar(table, orient="vertical", command=self.tree.yview)
        sx = ttk.Scrollbar(table, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=sy.set,xscrollcommand=sx.set)
        self.tree.grid(row=0,column=0,sticky="nsew")
        sy.grid(row=0,column=1,sticky="ns")
        sx.grid(row=1,column=0,sticky="ew")
        table.rowconfigure(0,weight=1); table.columnconfigure(0,weight=1)

    def _build_options(self, parent):
        self._section_title(parent, "PROCESSING OPTIONS", "BATCH SETTINGS")
        body = tk.Frame(parent,bg=WHITE)
        body.pack(fill="both",expand=True,padx=18,pady=15)

        self.max_w=tk.StringVar(value="1600")
        self.max_h=tk.StringVar(value="1200")
        self.quality=tk.StringVar(value="85")
        self.output_format=tk.StringVar(value="WEBP")
        self.rename_mode=tk.StringVar(value="Sequential Names")
        self.prefix=tk.StringVar(value="processed_")

        self.output_format.trace_add("write", lambda *_: self._refresh_output_previews())
        self.rename_mode.trace_add("write", lambda *_: self._refresh_output_previews())
        self.prefix.trace_add("write", lambda *_: self._refresh_output_previews())

        self._field(body,"Maximum Width (px)",self.max_w,0,0)
        self._field(body,"Maximum Height (px)",self.max_h,0,1)
        self._combo(body,"Output Format",self.output_format,["WEBP (Recommended)","JPG","PNG"],1,0)
        self._field(body,"Quality (1 - 100)",self.quality,1,1)
        self._combo(body,"File Naming",self.rename_mode,["Keep Original Names","Sequential Names"],2,0)
        self._field(body,"Filename Prefix",self.prefix,2,1)

        self.keep_ratio=tk.BooleanVar(value=True)
        self.skip_smaller=tk.BooleanVar(value=True)
        self.overwrite=tk.BooleanVar(value=False)
        self.open_after=tk.BooleanVar(value=True)

        for row,var,text in [(3,self.keep_ratio,"Maintain Aspect Ratio"),
                             (4,self.skip_smaller,"Skip smaller files"),
                             (3,self.overwrite,"Overwrite existing files"),
                             (4,self.open_after,"Open output folder")]:
            col=0 if text in ("Maintain Aspect Ratio","Skip if smaller than target size") else 1
            tk.Checkbutton(body,text=text,variable=var,bg=WHITE,fg=TEXT,
                           activebackground=WHITE,selectcolor=GREEN_LIGHT,
                           font=("Segoe UI",8),anchor="w").grid(row=row,column=col,sticky="w",pady=5)

        body.grid_columnconfigure(0,weight=1); body.grid_columnconfigure(1,weight=1)

        self.process_btn=self._button(body,"⚙  PROCESS IMAGES",self.start_processing,True)
        self.process_btn.configure(font=("Segoe UI",11,"bold"),pady=13)
        self.process_btn.grid(row=5,column=0,columnspan=2,sticky="ew",pady=(12,4))

        tk.Label(body,text="Tip: Use WEBP for smaller web-ready files. JPG is useful for compatibility.",
                 bg=WHITE,fg=MUTED,font=("Segoe UI",8),wraplength=385,justify="left").grid(
                     row=6,column=0,columnspan=2,sticky="w",pady=(4,0))

    def _field(self,parent,label,var,row,col):
        f=tk.Frame(parent,bg=WHITE)
        f.grid(row=row,column=col,sticky="ew",padx=5,pady=7)
        tk.Label(f,text=label,bg=WHITE,fg=TEXT,font=("Segoe UI",8,"bold")).pack(anchor="w")
        ttk.Entry(f,textvariable=var).pack(fill="x",pady=(4,0))

    def _combo(self,parent,label,var,values,row,col):
        f=tk.Frame(parent,bg=WHITE)
        f.grid(row=row,column=col,sticky="ew",padx=5,pady=7)
        tk.Label(f,text=label,bg=WHITE,fg=TEXT,font=("Segoe UI",8,"bold")).pack(anchor="w")
        cb=ttk.Combobox(f,textvariable=var,values=values,state="readonly")
        cb.pack(fill="x",pady=(4,0))
        if values: cb.current(0)

    def _build_progress(self,parent):
        panel=tk.Frame(parent,bg=WHITE,highlightbackground=BORDER,highlightthickness=1)
        panel.pack(side="left",fill="x",expand=True,padx=(0,6))
        self._section_title(panel,"PROCESSING PROGRESS")
        inside=tk.Frame(panel,bg=WHITE)
        inside.pack(fill="x",padx=14,pady=9)
        self.progress=ttk.Progressbar(inside,mode="determinate")
        self.progress.pack(side="left",fill="x",expand=True)
        self.progress_label=tk.Label(inside,text="0%",bg=WHITE,fg=TEXT,font=("Segoe UI",9,"bold"),width=5)
        self.progress_label.pack(side="right",padx=(10,0))
        self.progress_text=tk.Label(panel,text="Ready to process images.",bg=WHITE,fg=MUTED,font=("Segoe UI",8),anchor="w")
        self.progress_text.pack(fill="x",padx=14,pady=(1,8))

    def _build_summary(self,parent):
        panel=tk.Frame(parent,bg=WHITE,highlightbackground=BORDER,highlightthickness=1,width=610)
        panel.pack(side="right",fill="x",padx=(6,0))
        self._section_title(panel,"PROCESSING SUMMARY")
        inside=tk.Frame(panel,bg=WHITE)
        inside.pack(fill="both",expand=True,padx=12,pady=7)
        self.summary=tk.Label(inside,text="Total: 0   |   Processed: 0   |   Failed: 0   |   Input: 0 MB   |   Output: 0 MB",
                              bg=WHITE,fg=TEXT,font=("Segoe UI",8,"bold"),anchor="w")
        self.summary.pack(fill="x")
        actions=tk.Frame(inside,bg=WHITE)
        actions.pack(fill="x",pady=(8,0))
        self._button(actions,"▰  Open Folder",self.open_output).pack(side="right",padx=(6,0))
        self._button(actions,"▤  Create ZIP",self.create_zip).pack(side="right")

    def _status(self,text):
        if hasattr(self,"status"): self.status.config(text=text)

    def add_images(self):
        paths=filedialog.askopenfilenames(title="Select Images",
            filetypes=[("Image files","*.jpg *.jpeg *.png *.webp"),("All files","*.*")])
        self._add_paths(paths)

    def add_folder(self):
        folder=filedialog.askdirectory(title="Select Image Folder")
        if not folder:return
        paths=[str(p) for p in Path(folder).iterdir() if p.is_file() and p.suffix.lower() in SUPPORTED]
        self._add_paths(paths)

    def _add_paths(self,paths):
        existing={str(Path(p).resolve()) for p in self.files}
        added=0
        for p in paths:
            rp=str(Path(p).resolve())
            if rp in existing: continue
            try:
                with Image.open(p) as im: dims=f"{im.width} × {im.height}"
                kb=Path(p).stat().st_size/1024
                self.files.append(p)
                self.tree.insert("", "end", values=(Path(p).name,Path(p).suffix.upper().lstrip("."),
                    dims,f"{kb:.1f} KB","Ready",self._preview_output_name(len(self.files))))
                added+=1
            except Exception: pass
        self._refresh_count()
        self._status(f"{added} image(s) added | Ready")

    def _preview_output_name(self,n):
        fmt=self.output_format.get().split()[0].lower()
        ext=".jpg" if fmt=="jpg" else ".png" if fmt=="png" else ".webp"
        if self.rename_mode.get()=="Sequential Names": return f"{self.prefix.get() or 'processed_'}{n:03d}{ext}"
        return f"source_name{ext}"

    def _refresh_count(self):
        self.count_label.config(text=f"Total Files: {len(self.files)}")

    def remove_selected(self):
        selected=list(self.tree.selection())
        for item in selected:
            idx=self.tree.index(item)
            self.tree.delete(item)
            if idx < len(self.files): del self.files[idx]
        self._rebuild_rows()
        self._refresh_count()
        self._status("Selected files removed")

    def _rebuild_rows(self):
        paths=list(self.files)
        for item in self.tree.get_children(): self.tree.delete(item)
        self.files=[]
        self._add_paths(paths)

    def clear_list(self):
        self.files.clear()
        for item in self.tree.get_children(): self.tree.delete(item)
        self.results.clear()
        self._refresh_count()
        self._status("Queue cleared | Ready")


    def _refresh_output_previews(self):
        if not hasattr(self, "tree"):
            return
        fmt = self.output_format.get().split()[0].lower()
        ext = ".jpg" if fmt == "jpg" else ".png" if fmt == "png" else ".webp"
        children = self.tree.get_children()
        for i, item in enumerate(children, 1):
            vals = list(self.tree.item(item, "values"))
            if len(vals) >= 6:
                if self.rename_mode.get() == "Sequential Names":
                    vals[5] = f"{self.prefix.get() or 'processed_'}{i:03d}{ext}"
                else:
                    source_name = self.files[i-1] if i-1 < len(self.files) else ""
                    vals[5] = f"{Path(source_name).stem}{ext}" if source_name else ""
                self.tree.item(item, values=vals)

    def _read_settings(self):
        try:
            mw,mh,q=int(self.max_w.get()),int(self.max_h.get()),int(self.quality.get())
            if mw<=0 or mh<=0 or not 1<=q<=100: raise ValueError
        except ValueError: raise ValueError("Width, height and quality must be valid numbers.")
        fmt=self.output_format.get().split()[0]
        return mw,mh,q,fmt

    def start_processing(self):
        if self.processing:
            return
        if not self.files:
            self.show_message("No Images","Add one or more images before processing.","warning")
            return
        try: settings=self._read_settings()
        except ValueError as e:
            self.show_message("Invalid Settings",str(e),"warning"); return
        self.processing=True
        self.process_btn.config(state="disabled",bg=GREEN_DARK)
        self.results=[]
        self.progress["value"]=0
        self.progress_label.config(text="0%")
        for item in self.tree.get_children():
            vals=list(self.tree.item(item,"values")); vals[4]="Queued"; self.tree.item(item,values=vals)
        threading.Thread(target=self._worker,args=settings,daemon=True).start()
        self._status("Processing | Please wait...")

    def _worker(self,mw,mh,quality,fmt):
        outdir=Path.cwd()/"output"; outdir.mkdir(exist_ok=True)
        before=after=success=failed=0; total=len(self.files)
        sequential=self.rename_mode.get()=="Sequential Names"
        prefix=self.prefix.get().strip() or "processed_"
        for n,source in enumerate(self.files,1):
            try:
                src=Path(source)
                if src.stat().st_size>MAX_FILE_MB*1024*1024: raise ValueError(f"Over {MAX_FILE_MB} MB")
                with Image.open(src) as original:
                    img=ImageOps.exif_transpose(original)
                    before+=src.stat().st_size
                    if self.skip_smaller.get() and img.width<=mw and img.height<=mh:
                        resized=False
                    else:
                        ratio=min(mw/img.width,mh/img.height)
                        if ratio<1 or not self.keep_ratio.get():
                            if self.keep_ratio.get():
                                size=(max(1,round(img.width*ratio)),max(1,round(img.height*ratio)))
                            else: size=(mw,mh)
                            img=img.resize(size,Image.Resampling.LANCZOS); resized=True
                        else: resized=False
                    if fmt=="JPG":
                        if img.mode not in ("RGB","L"):
                            bg=Image.new("RGB",img.size,"white")
                            if "A" in img.getbands(): bg.paste(img,mask=img.getchannel("A"))
                            else: bg.paste(img)
                            img=bg
                        ext=".jpg"; kwargs={"quality":quality,"optimize":True}
                    elif fmt=="PNG":
                        if img.mode not in ("RGB","RGBA","L","LA"): img=img.convert("RGBA" if "A" in img.getbands() else "RGB")
                        ext=".png"; kwargs={"optimize":True}
                    else:
                        if img.mode not in ("RGB","RGBA"): img=img.convert("RGBA" if "A" in img.getbands() else "RGB")
                        ext=".webp"; kwargs={"quality":quality,"method":6}
                    name=f"{prefix}{n:03d}{ext}" if sequential else f"{src.stem}{ext}"
                    dst=outdir/name
                    if dst.exists() and not self.overwrite.get():
                        dst=outdir/f"{dst.stem}_{n}{dst.suffix}"
                    img.save(dst,**kwargs)
                    after+=dst.stat().st_size; success+=1; self.results.append(dst)
                    self.msg_queue.put(("row",n-1,"Completed",dst.name))
            except Exception as exc:
                failed+=1; self.msg_queue.put(("row",n-1,f"Failed: {exc}",""))
            self.msg_queue.put(("progress",n/total,success,failed,before,after))
        self.msg_queue.put(("done",success,failed,before,after,str(outdir)))

    def _poll_queue(self):
        try:
            while True:
                msg=self.msg_queue.get_nowait()
                if msg[0]=="row":
                    children=self.tree.get_children()
                    if msg[1]<len(children):
                        vals=list(self.tree.item(children[msg[1]],"values")); vals[4]=msg[2]; vals[5]=msg[3]
                        self.tree.item(children[msg[1]],values=vals)
                elif msg[0]=="progress":
                    _,p,s,f,b,a=msg
                    self.progress["value"]=p*100; self.progress_label.config(text=f"{p*100:.0f}%")
                    self.summary.config(text=f"Total: {len(self.files)}   |   Processed: {s}   |   Failed: {f}   |   Input: {b/1048576:.2f} MB   |   Output: {a/1048576:.2f} MB")
                    self.progress_text.config(text=f"Processing {s+f} of {len(self.files)} images...")
                elif msg[0]=="done":
                    _,s,f,b,a,out=msg
                    self.processing=False; self.process_btn.config(state="normal",bg=GREEN)
                    self.progress["value"]=100; self.progress_label.config(text="100%")
                    self.progress_text.config(text="Processing completed successfully!" if f==0 else f"Completed with {f} failed file(s).")
                    self._status(f"Processing Complete | {s} images processed successfully | Failed: {f} | Output: {out}")
                    if self.open_after.get(): self.open_output()
                    CompletionDialog(self,s,f,b/1048576,a/1048576,out)
                self.msg_queue.task_done()
        except queue.Empty: pass
        self.after(100,self._poll_queue)

    def open_output(self):
        path=Path.cwd()/"output"; path.mkdir(exist_ok=True)
        try: os.startfile(path)
        except AttributeError:
            import subprocess
            subprocess.Popen(["open" if os.name=="posix" else "xdg-open",str(path)])

    def create_zip(self):
        files=[p for p in (Path.cwd()/"output").iterdir() if p.is_file() and p.suffix.lower() in SUPPORTED]
        if not files:
            self.show_message("No Output","Process images before creating a ZIP.","warning"); return
        target=Path.cwd()/"output"/"processed_images.zip"
        with zipfile.ZipFile(target,"w",zipfile.ZIP_DEFLATED) as z:
            for p in files: z.write(p,p.name)
        self._status(f"ZIP created | {target}")
        self.show_message("ZIP Created",f"ZIP package created successfully.\\n\\n{target}","info")

    def show_message(self,title,message,kind="info"):
        # Native dialog retained for non-completion notices.
        if kind=="warning": messagebox.showwarning(title,message,parent=self)
        else: messagebox.showinfo(title,message,parent=self)

    def show_settings(self):
        self.show_message("Settings","Processing settings are available in the Processing Options panel.","info")

    def show_help(self):
        self.show_message("Help","1. Add images or a folder.\\n2. Choose resize/format settings.\\n3. Click Process Images.\\n4. Review the summary and output folder.\\n5. Create a ZIP when required.","info")

    def show_about(self):
        self.show_message("About","AKASH TECH SOLUTIONS\\nProject - Bulk Image Processing\\n\\nPython desktop automation using Tkinter and Pillow.","info")


if __name__ == "__main__":
    BulkImageProcessor().mainloop()

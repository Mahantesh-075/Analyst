import React, { useState, useRef } from 'react';
import { api } from '../api/client';
import { UploadCloud, FileSpreadsheet, AlertCircle, X, CheckCircle2, Sparkles } from 'lucide-react';

interface UploadModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (datasetId: string) => void;
}

export const UploadModal: React.FC<UploadModalProps> = ({ isOpen, onClose, onSuccess }) => {
  const [file, setFile] = useState<File | null>(null);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [uploading, setUploading] = useState(false);
  const [progressText, setProgressText] = useState('');
  const [error, setError] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);

  if (!isOpen) return null;

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const selected = e.target.files[0];
      setFile(selected);
      if (!name) {
        setName(selected.name.replace(/\.[^/.]+$/, '').replace(/[_-]/g, ' '));
      }
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const selected = e.dataTransfer.files[0];
      setFile(selected);
      if (!name) {
        setName(selected.name.replace(/\.[^/.]+$/, '').replace(/[_-]/g, ' '));
      }
    }
  };

  const handleUseSampleData = () => {
    // Realistic messy dataset representing NGO field operations with defects
    const sampleCsv = 
`beneficiary_id,name,contact_phone,age,contribution,join_date,region
1001,  Aarav Sharma  ,+91 9876543210,34,$1,250.00,2023-01-15,North
1002,Priya Patel,priya@example.com,N/A,$850.50,15/02/2023,West
1003,  Aarav Sharma  ,+91 9876543210,34,$1,250.00,2023-01-15,North
1004,Devendra Singh,,45,$3,400.00,2023-03-10,South
1005,Ananya Gupta,9988776655,29,missing,2023-04-12,East
1006,Kavita Rao,kavita@ngo.org,38,$2,100.00,2023-05-20,North
1007,Rohan Verma,rohan@example.com,142,$950.00,2023-06-01,West
1008,Sunita Joshi,sunita@domain.org,27,$1,800.00,2023-07-04,South
`;
    const blob = new Blob([sampleCsv], { type: 'text/csv' });
    const sampleFile = new File([blob], 'ngo_field_survey_messy.csv', { type: 'text/csv' });
    setFile(sampleFile);
    setName('NGO Field Beneficiary Survey');
    setDescription('Field survey with duplicates, currency symbols, outlier ages, and unmasked contacts.');
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) {
      setError('Please select a file to upload');
      return;
    }

    if (file.size > 200 * 1024 * 1024) {
      setError('File exceeds 200MB limit (Invariant 5)');
      return;
    }

    setError(null);
    setUploading(true);
    try {
      setProgressText('Requesting secure S3 presigned URL...');
      const { upload_url, s3_key } = await api.getUploadUrl(file.name, file.size);

      setProgressText('Streaming file securely to storage...');
      const uploadRes = await fetch(upload_url, {
        method: 'PUT',
        body: file,
        headers: {
          'Content-Type': file.type || 'application/octet-stream',
        },
      });

      if (!uploadRes.ok) {
        throw new Error(`Upload failed with status ${uploadRes.status}`);
      }

      setProgressText('Registering immutable dataset version (Invariant 1)...');
      const ds = await api.createDataset({
        name: name || file.name,
        source_filename: file.name,
        s3_key,
        description: description || undefined,
      });

      setProgressText('Executing deterministic Polars ingestion & profiling...');
      await api.triggerIngest(ds.id);

      onSuccess(ds.id);
      onClose();
    } catch (err: any) {
      setError(err.message || 'Upload and processing failed');
    } finally {
      setUploading(false);
      setProgressText('');
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm">
      <div className="relative w-full max-w-lg rounded-2xl border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900 p-6 shadow-2xl transition-colors duration-200">
        <button
          onClick={onClose}
          disabled={uploading}
          className="absolute right-4 top-4 rounded-lg p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600 dark:hover:bg-slate-800 dark:hover:text-slate-200 transition-colors"
        >
          <X className="h-5 w-5" />
        </button>

        <div className="text-center">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-sky-500/10 text-sky-500 dark:text-sky-400 border border-sky-500/20">
            <UploadCloud className="h-6 w-6" />
          </div>
          <h2 className="mt-3 text-xl font-bold text-slate-900 dark:text-white">Upload Dataset</h2>
          <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
            Hostile-upload inspection, magic-byte verification, and automatic deterministic profiling
          </p>
        </div>

        {/* Quick Sample Button */}
        <div className="mt-4 flex justify-center">
          <button
            type="button"
            onClick={handleUseSampleData}
            disabled={uploading}
            className="flex items-center gap-1.5 rounded-full border border-sky-500/30 bg-sky-500/10 px-3 py-1 text-xs font-medium text-sky-600 hover:bg-sky-500/20 dark:text-sky-400 transition-all"
          >
            <Sparkles className="h-3.5 w-3.5" />
            <span>Load Messy Demo Dataset (NGO Survey)</span>
          </button>
        </div>

        {error && (
          <div className="mt-4 flex items-center gap-2 rounded-lg border border-rose-500/30 bg-rose-500/10 p-3 text-xs text-rose-600 dark:text-rose-400">
            <AlertCircle className="h-4 w-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="mt-5 space-y-4">
          <div
            onDragOver={(e) => e.preventDefault()}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            className={`flex flex-col items-center justify-center rounded-xl border-2 border-dashed p-6 text-center cursor-pointer transition-all ${
              file
                ? 'border-emerald-500/50 bg-emerald-500/5'
                : 'border-slate-300 bg-slate-50 hover:border-sky-500/50 hover:bg-slate-100/80 dark:border-slate-800 dark:bg-slate-950/40 dark:hover:border-sky-500/50 dark:hover:bg-slate-950/70'
            }`}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".csv,.tsv,.xlsx,.parquet"
              onChange={handleFileChange}
              className="hidden"
            />
            {file ? (
              <div className="flex flex-col items-center gap-2">
                <CheckCircle2 className="h-8 w-8 text-emerald-500 dark:text-emerald-400" />
                <span className="text-xs font-semibold text-slate-900 dark:text-white">{file.name}</span>
                <span className="text-[11px] text-slate-500 dark:text-slate-400">
                  {(file.size / 1024).toFixed(1)} KB — Click or drag to replace
                </span>
              </div>
            ) : (
              <div className="flex flex-col items-center gap-2">
                <FileSpreadsheet className="h-8 w-8 text-slate-400 dark:text-slate-500" />
                <span className="text-xs font-medium text-slate-700 dark:text-slate-300">
                  Drag and drop CSV, TSV, XLSX, or Parquet
                </span>
                <span className="text-[11px] text-slate-400 dark:text-slate-500">Max size 200MB · 2M rows · 500 columns</span>
              </div>
            )}
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-700 dark:text-slate-300">Dataset Name</label>
            <input
              type="text"
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Beneficiary Survey 2026"
              className="mt-1 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-xs text-slate-900 placeholder-slate-400 focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500 dark:border-slate-800 dark:bg-slate-950/60 dark:text-slate-100 dark:placeholder-slate-500"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-700 dark:text-slate-300">Description (Optional)</label>
            <input
              type="text"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Context or notes about data provenance"
              className="mt-1 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-xs text-slate-900 placeholder-slate-400 focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500 dark:border-slate-800 dark:bg-slate-950/60 dark:text-slate-100 dark:placeholder-slate-500"
            />
          </div>

          {uploading && (
            <div className="rounded-xl border border-sky-500/20 bg-sky-500/5 p-3 text-center">
              <div className="text-xs font-medium text-sky-400 animate-pulse">{progressText}</div>
            </div>
          )}

          <button
            type="submit"
            disabled={uploading || !file}
            className="w-full rounded-xl bg-gradient-to-r from-sky-500 to-indigo-600 py-2.5 text-xs font-semibold text-white shadow-lg shadow-sky-500/25 hover:from-sky-400 hover:to-indigo-500 active:scale-[0.98] transition-all disabled:opacity-50"
          >
            {uploading ? 'Ingesting Dataset...' : 'Upload & Start Pipeline'}
          </button>
        </form>
      </div>
    </div>
  );
};

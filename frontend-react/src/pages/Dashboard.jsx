import React, { useState, useEffect } from 'react';
import api from '../api/axios';
import Navbar from '../components/Navbar';
import {
  Wallet,
  TrendingDown,
  Layers,
  UploadCloud,
  FileText,
  CheckCircle2,
  Trash2,
  Sparkles,
  Calendar,
  Tag,
  CreditCard,
  DollarSign,
  AlertCircle,
  RefreshCw,
  XCircle,
  PieChart as PieIcon,
  BarChart3,
  Receipt,
  Info
} from 'lucide-react';
import {
  PieChart,
  Pie,
  Cell,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Legend
} from 'recharts';

const COLORS = ['#10B981', '#3B82F6', '#F59E0B', '#EF4444', '#8B5CF6', '#EC4899'];
const CLUSTER_COLORS = ['#3B82F6', '#F59E0B', '#EF4444'];

export default function Dashboard() {
  // Data States
  const [categories, setCategories] = useState([]);
  const [transactions, setTransactions] = useState([]);
  const [insights, setInsights] = useState(null);
  const [loadingData, setLoadingData] = useState(true);

  // Receipt Scanner States
  const [receiptFile, setReceiptFile] = useState(null);
  const [receiptPreview, setReceiptPreview] = useState(null);
  const [isScanning, setIsScanning] = useState(false);
  const [scanSuccess, setScanSuccess] = useState(false);
  const [scanError, setScanError] = useState('');

  // Transaction Form States
  const [formData, setFormData] = useState({
    category_id: '',
    receipt_id: null,
    type: 'expense',
    amount: '',
    transaction_date: new Date().toISOString().split('T')[0],
    description: '',
    payment_method: 'qris',
  });
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formMessage, setFormMessage] = useState({ type: '', text: '' });

  // Filter state
  const [filterCategory, setFilterCategory] = useState('');

  // Format currency IDR
  const formatRupiah = (number) => {
    return new Intl.NumberFormat('id-ID', {
      style: 'currency',
      currency: 'IDR',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(number || 0);
  };

  // Fetch initial data
  const fetchData = async () => {
    setLoadingData(true);
    try {
      const [catRes, trxRes, insightRes] = await Promise.all([
        api.get('/categories'),
        api.get('/transactions?per_page=50'),
        api.get('/transactions/insights').catch(() => ({ data: { data: null } })),
      ]);

      setCategories(catRes.data.data || []);
      setTransactions(trxRes.data.data || []);
      if (insightRes.data?.data) {
        setInsights(insightRes.data.data);
      }
    } catch (err) {
      console.error('Error fetching dashboard data:', err);
    } finally {
      setLoadingData(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  // Handle Receipt Upload & OCR Scan
  const handleFileChange = (e) => {
    const file = e.target.files[0];
    if (file) {
      setReceiptFile(file);
      setReceiptPreview(URL.createObjectURL(file));
      setScanSuccess(false);
      setScanError('');
    }
  };

  const handleScanReceipt = async () => {
    if (!receiptFile) return;

    setIsScanning(true);
    setScanError('');
    setScanSuccess(false);

    const data = new FormData();
    data.append('file', receiptFile);

    try {
      const res = await api.post('/receipts/scan', data, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });

      const result = res.data.data;
      setScanSuccess(true);

      // Auto-match category from suggested_category
      let matchedCategoryId = '';
      if (result.suggested_category && categories.length > 0) {
        const found = categories.find(
          (c) => c.name.toLowerCase() === result.suggested_category.toLowerCase()
        );
        if (found) matchedCategoryId = found.id;
      }

      // Auto-fill transaction form
      setFormData((prev) => ({
        ...prev,
        receipt_id: result.receipt_id,
        amount: result.total_amount ? String(result.total_amount) : prev.amount,
        description: result.merchant_name || prev.description,
        transaction_date: result.transaction_date || prev.transaction_date,
        category_id: matchedCategoryId || prev.category_id || (categories[0]?.id || ''),
      }));
    } catch (err) {
      console.error('Error scanning receipt:', err);
      const errMsg =
        err.response?.data?.message || 'Gagal memproses struk. Pastikan service Python aktif.';
      setScanError(errMsg);
    } finally {
      setIsScanning(false);
    }
  };

  // Handle Transaction Submit
  const handleTransactionSubmit = async (e) => {
    e.preventDefault();
    setIsSubmitting(true);
    setFormMessage({ type: '', text: '' });

    if (!formData.category_id) {
      setFormMessage({ type: 'error', text: 'Pilih kategori pengeluaran terlebih dahulu.' });
      setIsSubmitting(false);
      return;
    }

    try {
      await api.post('/transactions', {
        ...formData,
        amount: parseFloat(formData.amount),
        category_id: parseInt(formData.category_id, 10),
      });

      setFormMessage({ type: 'success', text: 'Transaksi berhasil disimpan!' });

      // Reset form
      setFormData({
        category_id: categories[0]?.id || '',
        receipt_id: null,
        type: 'expense',
        amount: '',
        transaction_date: new Date().toISOString().split('T')[0],
        description: '',
        payment_method: 'qris',
      });
      setReceiptFile(null);
      setReceiptPreview(null);
      setScanSuccess(false);

      // Refresh data
      fetchData();
    } catch (err) {
      const errMsg = err.response?.data?.message || 'Gagal menyimpan transaksi.';
      setFormMessage({ type: 'error', text: errMsg });
    } finally {
      setIsSubmitting(false);
    }
  };

  // Handle Delete Transaction
  const handleDeleteTransaction = async (id) => {
    if (!window.confirm('Apakah Anda yakin ingin menghapus transaksi ini?')) return;

    try {
      await api.delete(`/transactions/${id}`);
      fetchData();
    } catch (err) {
      alert('Gagal menghapus transaksi.');
    }
  };

  // Calculations for Summary Cards
  const totalExpense = transactions
    .filter((t) => t.type === 'expense')
    .reduce((acc, curr) => acc + (parseFloat(curr.amount) || 0), 0);

  const totalTransactionsCount = transactions.length;

  // Chart Data: Expenses by Category
  const categoryChartData = categories
    .map((cat) => {
      const total = transactions
        .filter((t) => t.category_id === cat.id && t.type === 'expense')
        .reduce((sum, t) => sum + (parseFloat(t.amount) || 0), 0);
      return { name: cat.name, value: total };
    })
    .filter((item) => item.value > 0);

  // Chart Data: Clusters Summary
  const clusterChartData =
    insights?.clusters_summary?.map((c) => ({
      name: c.cluster_label.replace(/\s*\(.*?\)/, ''),
      total: c.total_spent,
      count: c.count,
    })) || [];

  // Filtered transactions for table
  const displayedTransactions = transactions.filter((t) => {
    if (!filterCategory) return true;
    return String(t.category_id) === String(filterCategory);
  });

  return (
    <div className="min-h-screen bg-slate-50 pb-16">
      <Navbar />

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-8 space-y-8">
        {/* SECTION 1: STATS SUMMARY CARDS */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
          {/* Card 1: Total Pengeluaran */}
          <div className="bg-white rounded-2xl p-6 border border-slate-200/80 shadow-sm hover:shadow-md transition-shadow">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                Total Pengeluaran
              </span>
              <div className="w-10 h-10 rounded-xl bg-red-50 text-red-600 flex items-center justify-center">
                <TrendingDown className="w-5 h-5" />
              </div>
            </div>
            <div className="mt-4">
              <h2 className="text-2xl sm:text-3xl font-bold text-slate-900 tracking-tight">
                {formatRupiah(totalExpense)}
              </h2>
              <p className="text-xs text-slate-400 mt-1">Akumulasi pengeluaran tercatat</p>
            </div>
          </div>

          {/* Card 2: Jumlah Transaksi */}
          <div className="bg-white rounded-2xl p-6 border border-slate-200/80 shadow-sm hover:shadow-md transition-shadow">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                Total Transaksi
              </span>
              <div className="w-10 h-10 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center">
                <Layers className="w-5 h-5" />
              </div>
            </div>
            <div className="mt-4">
              <h2 className="text-2xl sm:text-3xl font-bold text-slate-900 tracking-tight">
                {totalTransactionsCount} <span className="text-sm font-normal text-slate-400">catatan</span>
              </h2>
              <p className="text-xs text-slate-400 mt-1">Struk & transaksi tersimpan</p>
            </div>
          </div>

          {/* Card 3: AI Profil Klaster */}
          <div className="bg-gradient-to-br from-emerald-600 to-teal-700 rounded-2xl p-6 text-white shadow-md shadow-emerald-700/20">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold uppercase tracking-wider text-emerald-100 flex items-center gap-1.5">
                <Sparkles className="w-4 h-4" /> AI ML Segmentation
              </span>
              <span className="text-[11px] bg-white/20 px-2 py-0.5 rounded-full font-medium">
                {insights?.status === 'clustered' ? 'K-Means Aktif' : 'Status Awal'}
              </span>
            </div>
            <div className="mt-4">
              <h3 className="text-lg font-bold">
                {insights?.status === 'clustered'
                  ? '3 Klaster Pengeluaran'
                  : 'Siap Menganalisis'}
              </h3>
              <p className="text-xs text-emerald-100/90 mt-1 leading-relaxed">
                {insights?.insights?.[0] || 'Catat minimal 3 transaksi untuk mengaktifkan AI clustering.'}
              </p>
            </div>
          </div>
        </div>

        {/* SECTION 2: SMART RECEIPT SCANNER & TRANSACTION FORM */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
          {/* Left Column: Smart OCR Receipt Scanner (5 cols) */}
          <div className="lg:col-span-5 bg-white rounded-2xl p-6 border border-slate-200/80 shadow-sm flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <div className="w-8 h-8 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center">
                    <Receipt className="w-4 h-4" />
                  </div>
                  <div>
                    <h3 className="font-bold text-slate-900 text-base">Smart Receipt OCR</h3>
                    <p className="text-xs text-slate-400">Scan struk belanja fisik / QRIS</p>
                  </div>
                </div>
                <span className="text-[11px] font-semibold text-emerald-700 bg-emerald-50 px-2 py-1 rounded-md border border-emerald-100">
                  EasyOCR + OpenCV
                </span>
              </div>

              {/* Upload Drop Area */}
              <div className="mt-2 border-2 border-dashed border-slate-200 rounded-xl p-4 text-center hover:border-emerald-500 transition-colors bg-slate-50/50 relative">
                {receiptPreview ? (
                  <div className="space-y-3">
                    <img
                      src={receiptPreview}
                      alt="Preview Struk"
                      className="max-h-56 mx-auto rounded-lg object-contain shadow-sm border border-slate-200"
                    />
                    <div className="flex items-center justify-center gap-2">
                      <button
                        type="button"
                        onClick={() => {
                          setReceiptFile(null);
                          setReceiptPreview(null);
                          setScanSuccess(false);
                          setScanError('');
                        }}
                        className="text-xs text-red-600 hover:underline flex items-center gap-1"
                      >
                        <XCircle className="w-3.5 h-3.5" /> Ganti Gambar
                      </button>
                    </div>
                  </div>
                ) : (
                  <label className="cursor-pointer block py-8">
                    <UploadCloud className="w-10 h-10 text-emerald-500 mx-auto mb-2" />
                    <p className="text-sm font-semibold text-slate-700">Pilih atau Seret Foto Struk</p>
                    <p className="text-xs text-slate-400 mt-1">Mendukung format JPG, PNG, WEBP (Maks 10MB)</p>
                    <input
                      type="file"
                      accept="image/jpeg,image/png,image/webp"
                      onChange={handleFileChange}
                      className="hidden"
                    />
                  </label>
                )}
              </div>

              {/* Scan Error / Success Alerts */}
              {scanError && (
                <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-xl text-xs text-red-700 flex items-start gap-2">
                  <AlertCircle className="w-4 h-4 flex-shrink-0 text-red-500 mt-0.5" />
                  <span>{scanError}</span>
                </div>
              )}

              {scanSuccess && (
                <div className="mt-4 p-3 bg-emerald-50 border border-emerald-200 rounded-xl text-xs text-emerald-700 flex items-start gap-2">
                  <CheckCircle2 className="w-4 h-4 flex-shrink-0 text-emerald-600 mt-0.5" />
                  <div>
                    <span className="font-semibold">Berhasil diekstrak!</span>
                    <p className="text-[11px] text-emerald-600 mt-0.5">
                      Data struk telah otomatis disalin ke formulir transaksi di sebelah kanan.
                    </p>
                  </div>
                </div>
              )}
            </div>

            {/* Action Button */}
            <div className="mt-6 pt-4 border-t border-slate-100">
              <button
                type="button"
                onClick={handleScanReceipt}
                disabled={!receiptFile || isScanning}
                className="w-full py-3 px-4 bg-emerald-600 hover:bg-emerald-700 text-white font-medium rounded-xl text-sm transition-all shadow-md shadow-emerald-600/20 flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
              >
                {isScanning ? (
                  <>
                    <RefreshCw className="w-4 h-4 animate-spin" />
                    <span>Memproses OCR & AI Parser...</span>
                  </>
                ) : (
                  <>
                    <Sparkles className="w-4 h-4" />
                    <span>Ekstrak Data dari Struk</span>
                  </>
                )}
              </button>
            </div>
          </div>

          {/* Right Column: Transaction Input Form (7 cols) */}
          <div className="lg:col-span-7 bg-white rounded-2xl p-6 border border-slate-200/80 shadow-sm">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="font-bold text-slate-900 text-base">Catat Transaksi</h3>
                <p className="text-xs text-slate-400">Verifikasi hasil ekstraksi atau isi manual</p>
              </div>
              {formData.receipt_id && (
                <span className="text-[11px] font-semibold text-blue-700 bg-blue-50 px-2 py-1 rounded-md border border-blue-100 flex items-center gap-1">
                  <CheckCircle2 className="w-3.5 h-3.5" /> Terhubung dengan Struk #{formData.receipt_id}
                </span>
              )}
            </div>

            {formMessage.text && (
              <div
                className={`mb-5 p-3 rounded-xl text-xs flex items-center gap-2 ${
                  formMessage.type === 'success'
                    ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                    : 'bg-red-50 text-red-700 border border-red-200'
                }`}
              >
                {formMessage.type === 'success' ? (
                  <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                ) : (
                  <AlertCircle className="w-4 h-4 text-red-500" />
                )}
                <span>{formMessage.text}</span>
              </div>
            )}

            <form onSubmit={handleTransactionSubmit} className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {/* Nominal / Amount */}
                <div>
                  <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                    Nominal (Rp) *
                  </label>
                  <div className="relative">
                    <span className="absolute left-3.5 top-1/2 -translate-y-1/2 text-sm font-semibold text-slate-400">
                      Rp
                    </span>
                    <input
                      type="number"
                      required
                      step="any"
                      min="1"
                      value={formData.amount}
                      onChange={(e) => setFormData({ ...formData, amount: e.target.value })}
                      placeholder="0"
                      className="w-full pl-11 pr-4 py-2.5 rounded-xl border border-slate-200 text-slate-800 font-semibold focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent text-sm"
                    />
                  </div>
                </div>

                {/* Kategori */}
                <div>
                  <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                    Kategori *
                  </label>
                  <div className="relative">
                    <Tag className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
                    <select
                      required
                      value={formData.category_id}
                      onChange={(e) => setFormData({ ...formData, category_id: e.target.value })}
                      className="w-full pl-10 pr-4 py-2.5 rounded-xl border border-slate-200 text-slate-800 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent text-sm bg-white cursor-pointer"
                    >
                      <option value="">Pilih Kategori</option>
                      {categories.map((c) => (
                        <option key={c.id} value={c.id}>
                          {c.name}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
              </div>

              {/* Deskripsi / Nama Merchant */}
              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                  Deskripsi / Toko *
                </label>
                <div className="relative">
                  <FileText className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
                  <input
                    type="text"
                    required
                    value={formData.description}
                    onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                    placeholder="Contoh: Kopi Kenangan, Indomaret, dsb."
                    className="w-full pl-10 pr-4 py-2.5 rounded-xl border border-slate-200 text-slate-800 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent text-sm"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {/* Tanggal Transaksi */}
                <div>
                  <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                    Tanggal Transaksi *
                  </label>
                  <div className="relative">
                    <Calendar className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
                    <input
                      type="date"
                      required
                      value={formData.transaction_date}
                      onChange={(e) => setFormData({ ...formData, transaction_date: e.target.value })}
                      className="w-full pl-10 pr-4 py-2.5 rounded-xl border border-slate-200 text-slate-800 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent text-sm"
                    />
                  </div>
                </div>

                {/* Metode Pembayaran */}
                <div>
                  <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                    Metode Pembayaran
                  </label>
                  <div className="relative">
                    <CreditCard className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
                    <select
                      value={formData.payment_method}
                      onChange={(e) => setFormData({ ...formData, payment_method: e.target.value })}
                      className="w-full pl-10 pr-4 py-2.5 rounded-xl border border-slate-200 text-slate-800 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent text-sm bg-white cursor-pointer"
                    >
                      <option value="qris">QRIS</option>
                      <option value="cash">Tunai (Cash)</option>
                      <option value="transfer">Transfer Bank</option>
                      <option value="card">Kartu Debit/Kredit</option>
                    </select>
                  </div>
                </div>
              </div>

              <div className="pt-2 flex justify-end gap-3">
                <button
                  type="button"
                  onClick={() =>
                    setFormData({
                      category_id: categories[0]?.id || '',
                      receipt_id: null,
                      type: 'expense',
                      amount: '',
                      transaction_date: new Date().toISOString().split('T')[0],
                      description: '',
                      payment_method: 'qris',
                    })
                  }
                  className="px-4 py-2.5 rounded-xl border border-slate-200 text-slate-600 hover:bg-slate-50 text-sm font-medium transition-colors cursor-pointer"
                >
                  Reset
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="px-6 py-2.5 bg-emerald-600 hover:bg-emerald-700 active:bg-emerald-800 text-white rounded-xl text-sm font-medium transition-all shadow-md shadow-emerald-600/20 flex items-center gap-2 cursor-pointer disabled:opacity-70"
                >
                  {isSubmitting ? (
                    <>
                      <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                      <span>Menyimpan...</span>
                    </>
                  ) : (
                    <span>Simpan Transaksi</span>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>

        {/* SECTION 3: RECHARTS & AI INSIGHTS */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
          {/* Chart 1: Distribusi Kategori (Pie Chart) - 6 cols */}
          <div className="lg:col-span-6 bg-white rounded-2xl p-6 border border-slate-200/80 shadow-sm">
            <div className="flex items-center gap-2 mb-4">
              <PieIcon className="w-5 h-5 text-emerald-600" />
              <h3 className="font-bold text-slate-900 text-base">Distribusi Kategori Pengeluaran</h3>
            </div>
            {categoryChartData.length > 0 ? (
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={categoryChartData}
                      cx="50%"
                      cy="50%"
                      innerRadius={60}
                      outerRadius={90}
                      paddingAngle={4}
                      dataKey="value"
                    >
                      {categoryChartData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip
                      formatter={(val) => formatRupiah(val)}
                      contentStyle={{ borderRadius: '12px', border: '1px solid #e2e8f0' }}
                    />
                    <Legend verticalAlign="bottom" height={36} />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <div className="h-64 flex flex-col items-center justify-center text-slate-400 text-sm">
                <Info className="w-8 h-8 mb-2 stroke-1" />
                <span>Belum ada data pengeluaran untuk ditampilkan grafik.</span>
              </div>
            )}
          </div>

          {/* Chart 2: K-Means Clusters (Bar Chart) - 6 cols */}
          <div className="lg:col-span-6 bg-white rounded-2xl p-6 border border-slate-200/80 shadow-sm flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <BarChart3 className="w-5 h-5 text-blue-600" />
                  <h3 className="font-bold text-slate-900 text-base">Segmentasi Klaster K-Means</h3>
                </div>
                <span className="text-xs bg-slate-100 text-slate-600 px-2 py-0.5 rounded-full font-medium">
                  {insights?.status === 'clustered' ? '3 Profil' : 'Data Terbatas'}
                </span>
              </div>

              {clusterChartData.length > 0 ? (
                <div className="h-56">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={clusterChartData}>
                      <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                      <YAxis
                        tick={{ fontSize: 11 }}
                        tickFormatter={(val) => `Rp ${val / 1000}k`}
                      />
                      <Tooltip
                        formatter={(val) => formatRupiah(val)}
                        contentStyle={{ borderRadius: '12px', border: '1px solid #e2e8f0' }}
                      />
                      <Bar dataKey="total" radius={[8, 8, 0, 0]}>
                        {clusterChartData.map((entry, index) => (
                          <Cell
                            key={`bar-cell-${index}`}
                            fill={CLUSTER_COLORS[index % CLUSTER_COLORS.length]}
                          />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              ) : (
                <div className="h-56 flex flex-col items-center justify-center text-slate-400 text-sm">
                  <Info className="w-8 h-8 mb-2 stroke-1" />
                  <span>Grafik klastering membutuhkan minimal 3 transaksi.</span>
                </div>
              )}
            </div>

            {/* AI Insights Recommendations */}
            {insights?.insights && insights.insights.length > 0 && (
              <div className="mt-4 pt-4 border-t border-slate-100 bg-slate-50/70 p-3.5 rounded-xl border border-slate-100">
                <p className="text-xs font-semibold text-slate-700 flex items-center gap-1.5 mb-1.5">
                  <Sparkles className="w-3.5 h-3.5 text-emerald-600" /> Rekomendasi Finansial AI:
                </p>
                <ul className="text-xs text-slate-600 space-y-1 list-disc list-inside">
                  {insights.insights.map((msg, i) => (
                    <li key={i}>{msg}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </div>

        {/* SECTION 4: TRANSACTIONS HISTORY TABLE */}
        <div className="bg-white rounded-2xl border border-slate-200/80 shadow-sm overflow-hidden">
          <div className="p-6 border-b border-slate-100 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <div>
              <h3 className="font-bold text-slate-900 text-base">Riwayat Transaksi</h3>
              <p className="text-xs text-slate-400">Daftar seluruh catatan pengeluaran & pemasukan</p>
            </div>

            {/* Filter by Category */}
            <div className="flex items-center gap-3">
              <span className="text-xs font-medium text-slate-500">Filter:</span>
              <select
                value={filterCategory}
                onChange={(e) => setFilterCategory(e.target.value)}
                className="text-xs px-3 py-2 rounded-xl border border-slate-200 text-slate-700 bg-white focus:outline-none focus:ring-2 focus:ring-emerald-500 cursor-pointer"
              >
                <option value="">Semua Kategori</option>
                {categories.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-slate-600">
              <thead className="bg-slate-50/80 text-[11px] font-semibold text-slate-500 uppercase tracking-wider border-b border-slate-100">
                <tr>
                  <th className="px-6 py-3.5">Tanggal</th>
                  <th className="px-6 py-3.5">Deskripsi / Toko</th>
                  <th className="px-6 py-3.5">Kategori</th>
                  <th className="px-6 py-3.5">Metode</th>
                  <th className="px-6 py-3.5 text-right">Nominal</th>
                  <th className="px-6 py-3.5 text-center">Aksi</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {displayedTransactions.length > 0 ? (
                  displayedTransactions.map((trx) => (
                    <tr key={trx.id} className="hover:bg-slate-50/50 transition-colors">
                      <td className="px-6 py-4 whitespace-nowrap text-xs font-medium text-slate-500">
                        {trx.transaction_date}
                      </td>
                      <td className="px-6 py-4">
                        <div className="flex items-center gap-2">
                          <span className="font-semibold text-slate-800">{trx.description}</span>
                          {trx.receipt_id && (
                            <span
                              title="Tercatat dari struk OCR"
                              className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-emerald-50 text-emerald-700 border border-emerald-100"
                            >
                              Struk
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span
                          className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium"
                          style={{
                            backgroundColor: trx.category?.color ? `${trx.category.color}15` : '#f1f5f9',
                            color: trx.category?.color || '#475569',
                          }}
                        >
                          {trx.category?.name || 'Umum'}
                        </span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-xs uppercase font-medium text-slate-400">
                        {trx.payment_method}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-right font-bold text-slate-900">
                        {formatRupiah(trx.amount)}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-center">
                        <button
                          onClick={() => handleDeleteTransaction(trx.id)}
                          title="Hapus Transaksi"
                          className="p-1.5 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors cursor-pointer"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={6} className="px-6 py-10 text-center text-slate-400 text-xs">
                      Belum ada transaksi pada kategori ini.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </main>
    </div>
  );
}

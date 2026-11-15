<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use App\Models\Receipt;
use App\Services\ReceiptProcessorService;
use Exception;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Storage;

class ReceiptController extends Controller
{
    public function __construct(
        protected ReceiptProcessorService $processor
    ) {}

    /**
     * Upload dan ekstrak data struk belanja via Python OCR
     *
     * @param Request $request
     * @return JsonResponse
     */
    public function scan(Request $request): JsonResponse
    {
        $request->validate([
            'image' => ['required_without:file', 'file', 'image', 'mimes:jpeg,png,jpg,webp', 'max:10240'],
            'file' => ['required_without:image', 'file', 'image', 'mimes:jpeg,png,jpg,webp', 'max:10240'],
        ], [
            'image.required_without' => 'File gambar struk wajib diunggah.',
            'file.required_without' => 'File gambar struk wajib diunggah.',
            'image.image' => 'File harus berupa gambar (JPEG, PNG, WEBP).',
            'file.image' => 'File harus berupa gambar (JPEG, PNG, WEBP).',
            'image.max' => 'Ukuran file gambar maksimal 10MB.',
            'file.max' => 'Ukuran file gambar maksimal 10MB.',
        ]);

        $file = $request->file('image') ?? $request->file('file');

        // 1. Simpan gambar fisik ke storage/app/public/receipts
        $storedPath = $file->store('receipts', 'public');
        $publicUrl = asset(Storage::url($storedPath));

        try {
            // 2. Kirim ke Microservice Python OCR
            $ocrResult = $this->processor->extractReceipt($file);

            $parsedData = $ocrResult['data'] ?? [];
            $merchant = $parsedData['merchant_name'] ?? null;
            $totalAmount = $parsedData['total_amount'] ?? null;
            $trxDate = $parsedData['transaction_date'] ?? null;
            $suggestedCategory = $parsedData['suggested_category'] ?? null;
            $confidence = $ocrResult['confidence_score'] ?? 0.0;
            $rawText = $ocrResult['raw_text'] ?? null;

            // 3. Simpan record awal struk ke database
            $receipt = Receipt::create([
                'user_id' => $request->user()->id,
                'image_path' => $storedPath,
                'merchant_name' => $merchant,
                'receipt_date' => $trxDate,
                'total_amount' => $totalAmount,
                'confidence_score' => $confidence,
                'processing_status' => 'processed',
                'raw_ocr_text' => $rawText,
                'ocr_raw_payload' => $ocrResult,
            ]);

            return response()->json([
                'success' => true,
                'message' => 'Struk berhasil diproses dan diekstrak.',
                'data' => [
                    'receipt_id' => $receipt->id,
                    'receipt_image_path' => $storedPath,
                    'receipt_image_url' => $publicUrl,
                    'merchant_name' => $merchant,
                    'total_amount' => $totalAmount,
                    'transaction_date' => $trxDate,
                    'suggested_category' => $suggestedCategory,
                    'confidence_score' => $confidence,
                    'raw_text' => $rawText,
                ],
            ]);
        } catch (Exception $e) {
            // Catat receipt dengan status failed jika terjadi error pemrosesan
            Receipt::create([
                'user_id' => $request->user()->id,
                'image_path' => $storedPath,
                'processing_status' => 'failed',
                'raw_ocr_text' => $e->getMessage(),
            ]);

            return response()->json([
                'success' => false,
                'message' => 'Gagal mengekstrak teks dari struk: ' . $e->getMessage(),
                'receipt_image_path' => $storedPath,
                'receipt_image_url' => $publicUrl,
            ], 422);
        }
    }
}

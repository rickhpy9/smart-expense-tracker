<?php

namespace App\Services;

use Exception;
use Illuminate\Http\UploadedFile;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Log;

class ReceiptProcessorService
{
    protected string $baseUrl;
    protected string $token;
    protected int $timeout;

    public function __construct()
    {
        $this->baseUrl = rtrim(config('services.python.url', 'http://127.0.0.1:8001'), '/');
        $this->token = config('services.python.token', 'smart-expense-secret-key-2026');
        $this->timeout = (int) config('services.python.timeout', 90);
    }

    /**
     * Mengirim file gambar struk ke microservice Python OCR
     *
     * @param UploadedFile $file
     * @return array
     * @throws Exception
     */
    public function extractReceipt(UploadedFile $file): array
    {
        set_time_limit(120);
        
        $endpoint = "{$this->baseUrl}/api/v1/ocr/extract";

        try {
            $response = Http::timeout($this->timeout)
                ->withHeaders([
                    'x-service-token' => $this->token,
                    'Accept' => 'application/json',
                ])
                ->attach(
                    'file',
                    file_get_contents($file->getRealPath()),
                    $file->getClientOriginalName()
                )
                ->post($endpoint);

            if ($response->successful()) {
                return $response->json();
            }

            Log::error('Python OCR Service Error', [
                'status' => $response->status(),
                'body' => $response->body(),
            ]);

            throw new Exception(
                $response->json('detail') ?? 'Gagal memproses gambar pada microservice OCR Python.'
            );
        } catch (Exception $e) {
            Log::error('Python Service Connection Error (OCR)', [
                'message' => $e->getMessage(),
                'url' => $endpoint,
            ]);
            throw $e;
        }
    }

    /**
     * Mengirim array transaksi user ke microservice Python ML Clustering
     *
     * @param array $transactions
     * @return array
     * @throws Exception
     */
    public function clusterTransactions(array $transactions): array
    {
        $endpoint = "{$this->baseUrl}/api/v1/ml/cluster";

        try {
            $response = Http::timeout($this->timeout)
                ->withHeaders([
                    'x-service-token' => $this->token,
                    'Accept' => 'application/json',
                ])
                ->post($endpoint, $transactions);

            if ($response->successful()) {
                return $response->json();
            }

            Log::error('Python ML Service Error', [
                'status' => $response->status(),
                'body' => $response->body(),
            ]);

            throw new Exception(
                $response->json('detail') ?? 'Gagal memproses clustering pada microservice ML Python.'
            );
        } catch (Exception $e) {
            Log::error('Python Service Connection Error (ML)', [
                'message' => $e->getMessage(),
                'url' => $endpoint,
            ]);
            throw $e;
        }
    }
}

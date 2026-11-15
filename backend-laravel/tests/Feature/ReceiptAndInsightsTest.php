<?php

namespace Tests\Feature;

use App\Models\Category;
use App\Models\Transaction;
use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Http\UploadedFile;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Storage;
use Tests\TestCase;

class ReceiptAndInsightsTest extends TestCase
{
    use RefreshDatabase;

    protected function setUp(): void
    {
        parent::setUp();
        $this->seed();
    }

    public function test_user_can_scan_receipt_via_python_ocr_mock(): void
    {
        Storage::fake('public');
        Http::fake([
            '*/api/v1/ocr/extract' => Http::response([
                'success' => true,
                'confidence_score' => 0.95,
                'data' => [
                    'merchant_name' => 'Kopi Kenangan - Ruko Telagamas Semarang',
                    'total_amount' => 74000.0,
                    'transaction_date' => '2026-11-12',
                    'suggested_category' => 'Makanan & Minuman',
                ],
                'raw_text' => "Kopi Kenangan\nOutlet Name\nRuko Telagamas Semarang\nTotal\n74.00o",
                'lines' => ['Kopi Kenangan', 'Outlet Name', 'Ruko Telagamas Semarang', 'Total', '74.00o'],
            ], 200),
        ]);

        $user = User::factory()->create();
        $file = UploadedFile::fake()->create('receipt.jpg', 100, 'image/jpeg');

        $response = $this->actingAs($user, 'sanctum')->postJson('/api/receipts/scan', [
            'file' => $file,
        ]);

        $response->assertStatus(200)
            ->assertJsonPath('success', true)
            ->assertJsonPath('data.merchant_name', 'Kopi Kenangan - Ruko Telagamas Semarang')
            ->assertJsonPath('data.total_amount', 74000)
            ->assertJsonPath('data.transaction_date', '2026-11-12');

        $this->assertDatabaseHas('receipts', [
            'user_id' => $user->id,
            'merchant_name' => 'Kopi Kenangan - Ruko Telagamas Semarang',
            'total_amount' => 74000.00,
        ]);
    }

    public function test_user_can_get_transaction_insights_via_python_ml(): void
    {
        $user = User::factory()->create();
        $category = Category::where('name', 'Makanan & Minuman')->first();

        Transaction::create([
            'user_id' => $user->id,
            'category_id' => $category->id,
            'amount' => 50000,
            'type' => 'expense',
            'transaction_date' => '2026-11-15',
            'payment_method' => 'cash',
        ]);

        Http::fake([
            '*/api/v1/ml/cluster' => Http::response([
                'success' => true,
                'total_transactions' => 1,
                'status' => 'fallback',
                'clusters_summary' => [],
                'transactions' => [],
                'insights' => ['Data belum cukup'],
            ], 200),
        ]);

        $response = $this->actingAs($user, 'sanctum')->getJson('/api/transactions/insights');

        $response->assertStatus(200)
            ->assertJsonPath('success', true)
            ->assertJsonPath('data.status', 'fallback');
    }
}

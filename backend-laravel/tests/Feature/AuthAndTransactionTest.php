<?php

namespace Tests\Feature;

use App\Models\Category;
use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class AuthAndTransactionTest extends TestCase
{
    use RefreshDatabase;

    protected function setUp(): void
    {
        parent::setUp();
        $this->seed();
    }

    public function test_user_can_register(): void
    {
        $response = $this->postJson('/api/auth/register', [
            'name' => 'John Doe',
            'email' => 'john@example.com',
            'password' => 'password123',
            'password_confirmation' => 'password123',
        ]);

        $response->assertStatus(201)
            ->assertJsonPath('success', true)
            ->assertJsonStructure([
                'data' => [
                    'user' => ['id', 'name', 'email'],
                    'token',
                    'token_type',
                ],
            ]);

        $this->assertDatabaseHas('users', ['email' => 'john@example.com']);
    }

    public function test_user_can_login_and_logout(): void
    {
        $user = User::factory()->create([
            'email' => 'jane@example.com',
            'password' => bcrypt('password123'),
        ]);

        $loginResponse = $this->postJson('/api/auth/login', [
            'email' => 'jane@example.com',
            'password' => 'password123',
        ]);

        $loginResponse->assertStatus(200)
            ->assertJsonPath('success', true);

        $token = $loginResponse->json('data.token');

        $meResponse = $this->withHeader('Authorization', 'Bearer ' . $token)
            ->getJson('/api/auth/me');

        $meResponse->assertStatus(200)
            ->assertJsonPath('data.email', 'jane@example.com');

        $logoutResponse = $this->withHeader('Authorization', 'Bearer ' . $token)
            ->postJson('/api/auth/logout');

        $logoutResponse->assertStatus(200)
            ->assertJsonPath('success', true);
    }

    public function test_user_can_crud_transactions(): void
    {
        $user = User::factory()->create();
        $category = Category::where('name', 'Makanan & Minuman')->first();

        // 1. Create Transaction
        $createResponse = $this->actingAs($user, 'sanctum')->postJson('/api/transactions', [
            'category_id' => $category->id,
            'type' => 'expense',
            'amount' => 50000.00,
            'transaction_date' => '2026-11-15',
            'description' => 'Makan Siang Nasi Padang',
            'payment_method' => 'qris',
        ]);

        $createResponse->assertStatus(201)
            ->assertJsonPath('success', true)
            ->assertJsonPath('data.amount', 50000)
            ->assertJsonPath('data.description', 'Makan Siang Nasi Padang');

        $transactionId = $createResponse->json('data.id');

        // 2. List Transactions
        $listResponse = $this->actingAs($user, 'sanctum')->getJson('/api/transactions');
        $listResponse->assertStatus(200)
            ->assertJsonPath('success', true)
            ->assertJsonPath('meta.total', 1);

        // 3. Show Transaction
        $showResponse = $this->actingAs($user, 'sanctum')->getJson('/api/transactions/' . $transactionId);
        $showResponse->assertStatus(200)
            ->assertJsonPath('data.id', $transactionId);

        // 4. Update Transaction
        $updateResponse = $this->actingAs($user, 'sanctum')->putJson('/api/transactions/' . $transactionId, [
            'amount' => 65000.00,
            'description' => 'Makan Siang Nasi Padang Komplit',
        ]);

        $updateResponse->assertStatus(200)
            ->assertJsonPath('data.amount', 65000)
            ->assertJsonPath('data.description', 'Makan Siang Nasi Padang Komplit');

        // 5. Delete Transaction
        $deleteResponse = $this->actingAs($user, 'sanctum')->deleteJson('/api/transactions/' . $transactionId);
        $deleteResponse->assertStatus(200)
            ->assertJsonPath('success', true);

        $this->assertDatabaseMissing('transactions', ['id' => $transactionId]);
    }
}

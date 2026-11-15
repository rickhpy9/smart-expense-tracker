<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use App\Http\Requests\StoreTransactionRequest;
use App\Http\Requests\UpdateTransactionRequest;
use App\Http\Resources\TransactionResource;
use App\Models\Transaction;
use App\Services\ReceiptProcessorService;
use Exception;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;

class TransactionController extends Controller
{
    /**
     * Display a listing of the user's transactions.
     */
    public function index(Request $request): JsonResponse
    {
        $query = $request->user()->transactions()
            ->with(['category', 'receipt'])
            ->latest('transaction_date');

        if ($request->filled('category_id')) {
            $query->where('category_id', $request->category_id);
        }

        if ($request->filled('type')) {
            $query->where('type', $request->type);
        }

        if ($request->filled('start_date') && $request->filled('end_date')) {
            $query->whereBetween('transaction_date', [$request->start_date, $request->end_date]);
        }

        $perPage = $request->integer('per_page', 15);
        $transactions = $query->paginate($perPage);

        return response()->json([
            'success' => true,
            'data' => TransactionResource::collection($transactions),
            'meta' => [
                'current_page' => $transactions->currentPage(),
                'last_page' => $transactions->lastPage(),
                'per_page' => $transactions->perPage(),
                'total' => $transactions->total(),
            ],
        ]);
    }

    /**
     * Store a newly created transaction in storage.
     */
    public function store(StoreTransactionRequest $request): JsonResponse
    {
        $validated = $request->validated();
        $validated['user_id'] = $request->user()->id;

        $transaction = Transaction::create($validated);
        $transaction->load(['category', 'receipt']);

        return response()->json([
            'success' => true,
            'message' => 'Transaksi berhasil dicatat.',
            'data' => new TransactionResource($transaction),
        ], 201);
    }

    /**
     * Display the specified transaction.
     */
    public function show(Request $request, int $id): JsonResponse
    {
        $transaction = $request->user()->transactions()
            ->with(['category', 'receipt'])
            ->find($id);

        if (! $transaction) {
            return response()->json([
                'success' => false,
                'message' => 'Transaksi tidak ditemukan.',
            ], 404);
        }

        return response()->json([
            'success' => true,
            'data' => new TransactionResource($transaction),
        ]);
    }

    /**
     * Update the specified transaction in storage.
     */
    public function update(UpdateTransactionRequest $request, int $id): JsonResponse
    {
        $transaction = $request->user()->transactions()->find($id);

        if (! $transaction) {
            return response()->json([
                'success' => false,
                'message' => 'Transaksi tidak ditemukan.',
            ], 404);
        }

        $transaction->update($request->validated());
        $transaction->load(['category', 'receipt']);

        return response()->json([
            'success' => true,
            'message' => 'Transaksi berhasil diperbarui.',
            'data' => new TransactionResource($transaction),
        ]);
    }

    /**
     * Remove the specified transaction from storage.
     */
    public function destroy(Request $request, int $id): JsonResponse
    {
        $transaction = $request->user()->transactions()->find($id);

        if (! $transaction) {
            return response()->json([
                'success' => false,
                'message' => 'Transaksi tidak ditemukan.',
            ], 404);
        }

        $transaction->delete();

        return response()->json([
            'success' => true,
            'message' => 'Transaksi berhasil dihapus.',
        ]);
    }

    /**
     * Analisis klastering transaksi dan wawasan finansial via Python ML service
     */
    public function insights(Request $request, ReceiptProcessorService $processor): JsonResponse
    {
        $transactions = $request->user()->transactions()
            ->with('category')
            ->where('type', 'expense')
            ->latest('transaction_date')
            ->get();

        $payload = $transactions->map(function ($t) {
            return [
                'id' => $t->id,
                'amount' => (float) $t->amount,
                'category_name' => $t->category?->name ?? 'Lainnya',
                'transaction_date' => $t->transaction_date?->format('Y-m-d'),
                'description' => $t->description ?? '',
            ];
        })->values()->all();

        try {
            $analysis = $processor->clusterTransactions($payload);

            return response()->json([
                'success' => true,
                'message' => 'Analisis klaster pengeluaran berhasil diambil.',
                'data' => $analysis,
            ]);
        } catch (Exception $e) {
            return response()->json([
                'success' => false,
                'message' => 'Gagal mengambil analisis klaster transaksi: ' . $e->getMessage(),
            ], 500);
        }
    }
}

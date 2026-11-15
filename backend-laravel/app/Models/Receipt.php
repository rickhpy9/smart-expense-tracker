<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Database\Eloquent\Relations\HasOne;

class Receipt extends Model
{
    use HasFactory;

    protected $fillable = [
        'user_id',
        'image_path',
        'merchant_name',
        'receipt_date',
        'subtotal',
        'tax',
        'total_amount',
        'confidence_score',
        'processing_status', // 'pending', 'processed', 'failed'
        'raw_ocr_text',
        'ocr_raw_payload',
    ];

    protected function casts(): array
    {
        return [
            'receipt_date' => 'date',
            'subtotal' => 'decimal:2',
            'tax' => 'decimal:2',
            'total_amount' => 'decimal:2',
            'confidence_score' => 'float',
            'ocr_raw_payload' => 'array',
        ];
    }

    public function user(): BelongsTo
    {
        return $this->belongsTo(User::class);
    }

    public function transaction(): HasOne
    {
        return $this->hasOne(Transaction::class);
    }
}

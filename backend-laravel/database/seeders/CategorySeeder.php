<?php

namespace Database\Seeders;

use App\Models\Category;
use Illuminate\Database\Seeder;

class CategorySeeder extends Seeder
{
    /**
     * Run the database seeds.
     */
    public function run(): void
    {
        $categories = [
            [
                'name' => 'Makanan & Minuman',
                'icon' => 'utensils',
                'color' => '#EF4444',
                'type' => 'expense',
            ],
            [
                'name' => 'Transportasi',
                'icon' => 'car',
                'color' => '#3B82F6',
                'type' => 'expense',
            ],
            [
                'name' => 'Belanja',
                'icon' => 'shopping-bag',
                'color' => '#10B981',
                'type' => 'expense',
            ],
            [
                'name' => 'Tagihan',
                'icon' => 'receipt',
                'color' => '#F59E0B',
                'type' => 'expense',
            ],
            [
                'name' => 'Hiburan',
                'icon' => 'gamepad-2',
                'color' => '#8B5CF6',
                'type' => 'expense',
            ],
            [
                'name' => 'Gaji & Pemasukan',
                'icon' => 'wallet',
                'color' => '#059669',
                'type' => 'income',
            ],
        ];

        foreach ($categories as $cat) {
            Category::firstOrCreate(
                ['name' => $cat['name'], 'user_id' => null],
                $cat
            );
        }
    }
}

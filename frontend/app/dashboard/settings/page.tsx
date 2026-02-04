'use client';

import React, { useEffect, useState } from 'react';
import { useForm } from 'react-hook-form';
import { Save, Store, Theater, Lightbulb, Loader2 } from 'lucide-react';

interface SettingsFormData {
    business_name: string;
    business_type: string;
    other_business_type?: string;
    ai_tone: 'Formal' | 'Friendly' | 'Sales';
    products_services: string;
}

export default function SettingsPage() {
    const { register, handleSubmit, watch, reset } = useForm<SettingsFormData>({
        defaultValues: {
            ai_tone: 'Friendly',
            business_type: 'Other'
        }
    });

    const [isLoading, setIsLoading] = useState(true);
    const [isSaving, setIsSaving] = useState(false);

    // Watch business_type to conditionally show "Other" input
    const selectedBusinessType = watch('business_type');

    useEffect(() => {
        const fetchSettings = async () => {
            try {
                const token = localStorage.getItem('token');
                if (!token) {
                    // Ideally redirect to login here
                    return;
                }

                const res = await fetch('/api/v1/settings/', {
                    headers: {
                        'Authorization': `Bearer ${token}`
                    }
                });

                if (res.ok) {
                    const data = await res.json();

                    // Logic: If the returned business type is not in our standard list,
                    // set the select to 'Other' and the input to the actual value.
                    const standardTypes = ['Real Estate Agent', 'Fitness Coach', 'Sales', 'Consulting'];
                    let type = data.business_type;
                    let otherType = '';

    if (data.business_type && !standardTypes.includes(data.business_type)) {
        type = 'Other';
        otherType = data.business_type;
    } else if (!data.business_type) {
        type = 'Other'; // Default if empty
    }

    reset({
        business_name: data.business_name || '',
        business_type: type,
        other_business_type: otherType,
        ai_tone: data.ai_tone || 'Friendly',
        products_services: data.products_services || ''
    });
                }
            } catch (error) {
                console.error("Failed to fetch settings", error);
            } finally {
                setIsLoading(false);
            }
        };

        fetchSettings();
    }, [reset]);

    const onSubmit = async (data: SettingsFormData) => {
        setIsSaving(true);
        try {
            const token = localStorage.getItem('token');

            // If 'Other' is selected, use the text input value as the business_type
            const payload = {
                ...data,
                business_type: data.business_type === 'Other' ? data.other_business_type : data.business_type
            };
            // Clean up the temporary field before sending
            delete (payload as any).other_business_type;

            const res = await fetch('/api/v1/settings/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify(payload)
            });

            if (res.ok) {
                alert('✅ Settings saved successfully!');
            } else {
                alert('❌ Failed to save settings.');
            }
        } catch (error) {
            alert('❌ Network error.');
        } finally {
            setIsSaving(false);
        }
    };

    if (isLoading) {
        return (
            <div className="min-h-screen flex items-center justify-center bg-slate-50">
            <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-slate-50 pb-24 font-sans text-slate-800" dir="rtl">
        {/* Header */}
        <header className="bg-white border-b border-slate-200 sticky top-0 z-40 p-4 shadow-sm">
        <div className="max-w-xl mx-auto flex justify-between items-center">
        <h1 className="font-black text-lg flex items-center gap-2">
        <span className="text-xl">⚙️</span> מוח ה-AI
        </h1>
        </div>
        </header>

        <main className="max-w-xl mx-auto p-4 space-y-6">

        {/* Info Card */}
        <div className="bg-gradient-to-br from-blue-500 to-indigo-600 text-white p-5 rounded-2xl shadow-lg shadow-blue-500/20">
        <div className="flex items-start gap-4">
        <div className="bg-white/20 p-2 rounded-lg backdrop-blur-sm">
        <Store className="w-6 h-6" />
        </div>
        <div>
        <h3 className="font-bold text-sm">איך הבוט מתנהג?</h3>
        <p className="text-xs text-blue-100 mt-1 leading-relaxed">
        ההגדרות כאן משפיעות ישירות על התשובות שג'מיני ינסח עבורך בוואטסאפ.
        </p>
        </div>
        </div>
        </div>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">

        {/* Identity Section */}
        <div className="bg-white p-5 rounded-2xl shadow-sm border border-slate-100 space-y-4">
        <div className="flex items-center gap-2 border-b border-slate-50 pb-2 mb-2">
        <Store className="w-5 h-5 text-blue-500" />
        <h2 className="font-bold text-slate-800 text-sm">זהות העסק</h2>
        </div>

        <div>
        <label className="block text-xs font-bold text-slate-500 mb-1.5">שם העסק (כפי שיוצג ללקוח)</label>
        <input
        {...register('business_name')}
        type="text"
        className="w-full px-4 py-3 bg-slate-50 rounded-xl border border-slate-200 focus:ring-2 focus:ring-blue-500 outline-none text-sm font-medium transition"
        placeholder="למשל: דני כהן נדל״ן"
        />
        </div>

        <div>
        <label className="block text-xs font-bold text-slate-500 mb-1.5">תחום עיסוק</label>
        <select
        {...register('business_type')}
        className="w-full px-4 py-3 bg-slate-50 rounded-xl border border-slate-200 outline-none text-sm focus:ring-2 focus:ring-blue-500 transition"
        >
        <option value="Real Estate Agent">נדל"ן</option>
        <option value="Fitness Coach">כושר ובריאות</option>
        <option value="Sales">מכירות כללי</option>
        <option value="Consulting">ייעוץ</option>
        <option value="Other">אחר</option>
        </select>
        </div>

        {selectedBusinessType === 'Other' && (
            <div>
            <label className="block text-xs font-bold text-slate-500 mb-1.5">פרט את התחום</label>
            <input
            {...register('other_business_type')}
            type="text"
            className="w-full px-4 py-3 bg-slate-50 rounded-xl border border-slate-200 focus:ring-2 focus:ring-blue-500 outline-none text-sm font-medium transition animate-in fade-in slide-in-from-top-1"
            placeholder="למשל: אינסטלטור, מורה לפסנתר..."
            />
            </div>
        )}
        </div>

        {/* Tone Section */}
        <div className="bg-white p-5 rounded-2xl shadow-sm border border-slate-100 space-y-4">
        <div className="flex items-center gap-2 border-b border-slate-50 pb-2 mb-2">
        <Theater className="w-5 h-5 text-purple-500" />
        <h2 className="font-bold text-slate-800 text-sm">סגנון דיבור</h2>
        </div>

        <div className="grid grid-cols-3 gap-3">
        {/* Formal */}
        <label className="cursor-pointer relative group">
        <input
        type="radio"
        value="Formal"
        {...register('ai_tone')}
        className="peer sr-only"
        />
        <div className="p-3 text-center rounded-xl border border-slate-200 bg-slate-50 peer-checked:bg-slate-800 peer-checked:text-white peer-checked:border-slate-800 transition hover:bg-slate-100 group-active:scale-95">
        <div className="text-xl mb-1">👔</div>
        <span className="text-xs font-bold">רשמי</span>
        </div>
        </label>

        {/* Friendly */}
        <label className="cursor-pointer relative group">
        <input
        type="radio"
        value="Friendly"
        {...register('ai_tone')}
        className="peer sr-only"
        />
        <div className="p-3 text-center rounded-xl border border-slate-200 bg-slate-50 peer-checked:bg-slate-800 peer-checked:text-white peer-checked:border-slate-800 transition hover:bg-slate-100 group-active:scale-95">
        <div className="text-xl mb-1">👋</div>
        <span className="text-xs font-bold">חברי</span>
        </div>
        </label>

        {/* Sales */}
        <label className="cursor-pointer relative group">
        <input
        type="radio"
        value="Sales"
        {...register('ai_tone')}
        className="peer sr-only"
        />
        <div className="p-3 text-center rounded-xl border border-slate-200 bg-slate-50 peer-checked:bg-slate-800 peer-checked:text-white peer-checked:border-slate-800 transition hover:bg-slate-100 group-active:scale-95">
        <div className="text-xl mb-1">🔥</div>
        <span className="text-xs font-bold">מכירתי</span>
        </div>
        </label>
        </div>
        </div>

        {/* Knowledge Section */}
        <div className="bg-white p-5 rounded-2xl shadow-sm border border-slate-100 space-y-4">
        <div className="flex items-center gap-2 border-b border-slate-50 pb-2 mb-2">
        <Lightbulb className="w-5 h-5 text-yellow-500" />
        <h2 className="font-bold text-slate-800 text-sm">ידע עסקי</h2>
        </div>

        <div>
        <label className="block text-xs font-bold text-slate-500 mb-1.5">המוצרים/שירותים שלך</label>
        <textarea
        {...register('products_services')}
        rows={5}
        className="w-full p-3 bg-slate-50 rounded-xl border border-slate-200 focus:ring-2 focus:ring-blue-500 outline-none text-sm transition resize-none"
        placeholder={`למשל:\n- אימון אישי: 250 ש״ח\n- מנוי חודשי: 400 ש״ח\n- שעות פתיחה: 08:00 עד 20:00`}
        ></textarea>
        </div>
        </div>

        {/* Submit Button */}
        <button
        type="submit"
        disabled={isSaving}
        className="w-full bg-blue-600 text-white py-4 rounded-xl font-bold shadow-lg shadow-blue-500/30 hover:bg-blue-700 transition active:scale-95 disabled:opacity-70 disabled:active:scale-100 fixed bottom-6 left-4 right-4 max-w-xl mx-auto z-40 flex items-center justify-center gap-2"
        >
        {isSaving ? (
            <>
            <Loader2 className="w-5 h-5 animate-spin" />
            שומר...
            </>
        ) : (
            <>
            <Save className="w-5 h-5" />
            שמור שינויים
            </>
        )}
        </button>
        </form>
        </main>
        </div>
    );
}

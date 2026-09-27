import { useState } from 'react'
import BottomSheet from '../../components/BottomSheet'
import { Field, PrimaryButton, Select, TextInput } from '../../components/form'
import { ApiError } from '../../lib/apiClient'
import type { Labourer, PaymentFrequency } from './api'
import { useCreateLabourer, useUpdateLabourer } from './useLabourers'

interface LabourerFormSheetProps {
  labourer?: Labourer | null
  onClose: () => void
}

export default function LabourerFormSheet({ labourer, onClose }: LabourerFormSheetProps) {
  const isEdit = Boolean(labourer)
  const [name, setName] = useState(labourer?.name ?? '')
  const [phone, setPhone] = useState(labourer?.phone ?? '')
  const [upiId, setUpiId] = useState(labourer?.upi_id ?? '')
  const [workCategory, setWorkCategory] = useState(labourer?.work_category ?? '')
  const [paymentFrequency, setPaymentFrequency] = useState<PaymentFrequency>(
    labourer?.payment_frequency ?? 'daily'
  )
  const [error, setError] = useState<string | null>(null)

  const createMutation = useCreateLabourer()
  const updateMutation = useUpdateLabourer()
  const isSaving = createMutation.isPending || updateMutation.isPending

  async function handleSave() {
    setError(null)
    if (!name.trim()) {
      setError('Name is required')
      return
    }

    try {
      if (isEdit && labourer) {
        await updateMutation.mutateAsync({
          id: labourer.id,
          input: {
            name: name.trim(),
            phone: phone.trim() || null,
            upi_id: upiId.trim() || null,
            work_category: workCategory.trim() || null,
            payment_frequency: paymentFrequency,
          },
        })
      } else {
        await createMutation.mutateAsync({
          name: name.trim(),
          phone: phone.trim() || undefined,
          upi_id: upiId.trim() || undefined,
          work_category: workCategory.trim() || undefined,
          payment_frequency: paymentFrequency,
        })
      }
      onClose()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Something went wrong. Please try again.')
    }
  }

  return (
    <BottomSheet title={isEdit ? 'Edit labourer' : 'Add labourer'} onClose={onClose}>
      <div className="flex flex-col gap-4">
        <Field label="Name" htmlFor="labourer-name">
          <TextInput
            id="labourer-name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Full name"
            autoFocus={!isEdit}
          />
        </Field>

        <Field label="Phone (optional)" htmlFor="labourer-phone">
          <TextInput
            id="labourer-phone"
            type="tel"
            value={phone ?? ''}
            onChange={(e) => setPhone(e.target.value)}
            placeholder="10-digit number"
          />
        </Field>

        <Field label="UPI ID (optional)" htmlFor="labourer-upi-id">
          <TextInput
            id="labourer-upi-id"
            value={upiId ?? ''}
            onChange={(e) => setUpiId(e.target.value)}
            placeholder="e.g. 9876543210@ybl"
          />
        </Field>

        <Field label="Work category (optional)" htmlFor="labourer-category">
          <TextInput
            id="labourer-category"
            value={workCategory ?? ''}
            onChange={(e) => setWorkCategory(e.target.value)}
            placeholder="e.g. Mason, Helper, Electrician"
          />
        </Field>

        <Field label="Payment frequency" htmlFor="labourer-frequency">
          <Select
            id="labourer-frequency"
            value={paymentFrequency}
            onChange={(e) => setPaymentFrequency(e.target.value as PaymentFrequency)}
          >
            <option value="daily">Daily</option>
            <option value="weekly">Weekly</option>
          </Select>
        </Field>

        {error && <p className="text-sm text-rose-600">{error}</p>}

        <PrimaryButton onClick={handleSave} disabled={isSaving} className="w-full">
          {isSaving ? 'Saving…' : isEdit ? 'Save changes' : 'Add labourer'}
        </PrimaryButton>
      </div>
    </BottomSheet>
  )
}

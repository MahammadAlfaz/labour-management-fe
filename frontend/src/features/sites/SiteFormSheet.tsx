import { useState } from 'react'
import BottomSheet from '../../components/BottomSheet'
import {
  DangerButton,
  Field,
  PrimaryButton,
  TextArea,
  TextInput,
} from '../../components/form'
import PhotoUploader from '../../components/PhotoUploader'
import { BuildingIcon } from '../../components/icons'
import { ApiError } from '../../lib/apiClient'
import type { Site } from './api'
import SiteFinancePanel from './SiteFinancePanel'
import SiteWallCalculationsPanel from './SiteWallCalculationsPanel'
import {
  useRemoveSitePhoto,
  useSetSiteActive,
  useUpdateSite,
  useCreateSite,
  useUploadSitePhoto,
} from './useSites'

export default function SiteFormSheet({ site, onClose }: { site?: Site | null; onClose: () => void }) {
  const isEdit = Boolean(site)
  const [tab, setTab] = useState<'details' | 'finances' | 'wall-calculations'>('details')
  const [name, setName] = useState(site?.name ?? '')
  const [location, setLocation] = useState(site?.location ?? '')
  const [description, setDescription] = useState(site?.description ?? '')
  const [contractAmount, setContractAmount] = useState(site?.contract_amount ?? '')
  const [error, setError] = useState<string | null>(null)

  const createMutation = useCreateSite()
  const updateMutation = useUpdateSite()
  const setActiveMutation = useSetSiteActive()
  const uploadPhotoMutation = useUploadSitePhoto()
  const removePhotoMutation = useRemoveSitePhoto()
  const isSaving = createMutation.isPending || updateMutation.isPending

  async function handleSave() {
    setError(null)
    if (!name.trim() || !location.trim()) {
      setError('Name and location are required')
      return
    }

    try {
      if (isEdit && site) {
        await updateMutation.mutateAsync({
          id: site.id,
          input: { name: name.trim(), location: location.trim(), description: description.trim() || null, contract_amount: contractAmount || null },
        })
      } else {
        await createMutation.mutateAsync({
          name: name.trim(),
          location: location.trim(),
          description: description.trim() || undefined,
          contract_amount: contractAmount || undefined,
        })
      }
      onClose()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Something went wrong. Please try again.')
    }
  }

  return (
    <BottomSheet title={isEdit ? 'Edit site' : 'Add site'} onClose={onClose}>
      <div className="flex flex-col gap-4">
        {isEdit && (
          <div className="grid grid-cols-3 rounded-xl bg-slate-100 p-1" role="tablist" aria-label="Site sections">
            <button
              type="button"
              role="tab"
              aria-selected={tab === 'details'}
              onClick={() => setTab('details')}
              className={`min-h-11 rounded-lg px-2 text-sm font-semibold transition-colors ${tab === 'details' ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-600 active:bg-slate-200'}`}
            >
              Site details
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={tab === 'finances'}
              onClick={() => setTab('finances')}
              className={`min-h-11 rounded-lg px-2 text-sm font-semibold transition-colors ${tab === 'finances' ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-600 active:bg-slate-200'}`}
            >
              Finances
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={tab === 'wall-calculations'}
              onClick={() => setTab('wall-calculations')}
              className={`min-h-11 rounded-lg px-2 text-sm font-semibold transition-colors ${tab === 'wall-calculations' ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-600 active:bg-slate-200'}`}
            >
              Wall calculation
            </button>
          </div>
        )}

        {isEdit && site && tab === 'finances' && <SiteFinancePanel siteId={site.id} />}
        {isEdit && site && tab === 'wall-calculations' && <SiteWallCalculationsPanel siteId={site.id} />}

        {(!isEdit || tab === 'details') && <>
        {isEdit && site && (
          <PhotoUploader
            photoUrl={site.photo_url}
            onUpload={(file) => uploadPhotoMutation.mutateAsync({ id: site.id, file })}
            onRemove={() => removePhotoMutation.mutateAsync(site.id)}
            isUploading={uploadPhotoMutation.isPending}
            isRemoving={removePhotoMutation.isPending}
            label="photo"
            PlaceholderIcon={BuildingIcon}
          />
        )}

        <Field label="Site name" htmlFor="site-name">
          <TextInput
            id="site-name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. Tower A"
            autoFocus={!isEdit}
          />
        </Field>

        <Field label="Location" htmlFor="site-location">
          <TextInput
            id="site-location"
            value={location}
            onChange={(e) => setLocation(e.target.value)}
            placeholder="e.g. Sector 12, Pune"
          />
        </Field>

        <Field label="Description (optional)" htmlFor="site-description">
          <TextArea
            id="site-description"
            value={description ?? ''}
            onChange={(e) => setDescription(e.target.value)}
            rows={3}
          />
        </Field>

        <Field label="Agreed amount from client (optional)" htmlFor="site-contract-amount">
          <TextInput id="site-contract-amount" type="number" inputMode="decimal" min="0" step="0.01" value={contractAmount} onChange={(e) => setContractAmount(e.target.value)} placeholder="0.00" />
        </Field>

        {error && <p className="text-sm text-rose-600">{error}</p>}

        <PrimaryButton onClick={handleSave} disabled={isSaving} className="w-full">
          {isSaving ? 'Saving…' : isEdit ? 'Save changes' : 'Add site'}
        </PrimaryButton>

        {isEdit && site && (
          <DangerButton
            onClick={() => {
              setActiveMutation.mutate({ id: site.id, isActive: site.status !== 'active' })
              onClose()
            }}
            disabled={setActiveMutation.isPending}
            className="w-full"
          >
            {site.status === 'active' ? 'Close site' : 'Reopen site'}
          </DangerButton>
        )}

        </>}
      </div>
    </BottomSheet>
  )
}

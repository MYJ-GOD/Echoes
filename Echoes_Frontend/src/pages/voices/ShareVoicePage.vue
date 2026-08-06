<template>
  <div class="share-voice-page">
    <!-- 鎻愮ず淇℃伅 -->
    <div class="share-tip">
      <span class="tip-icon">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="12" cy="12" r="9" />
        <path d="M12 8v4" />
        <circle cx="12" cy="16" r="1" />
      </svg>
    </span>
      <span>{{ t("voices.shareTip") }}</span>
    </div>

    <!-- 鍒嗕韩缁欏搴垚鍛?-->
    <section class="share-section">
      <h3>{{ t("voices.shareToFamily") }}</h3>
      
      <div v-if="familyLoading" class="loading-state">
        <div class="mini-spinner"></div>
        <span>{{ t("voices.loadingFamilies") }}</span>
      </div>
      
      <div v-else-if="!isInFamily" class="family-notice">
        <p>{{ t("voices.notInFamily") }}</p>
        <router-link class="primary-link" to="/families">
          {{ t("voices.createFamily") }}
        </router-link>
      </div>
      
      <div v-else-if="familyMembers.length === 0" class="empty-members">
        <p>{{ t("voices.noFamilyMembers") }}</p>
      </div>
      
      <div v-else class="member-list">
        <div
          v-for="member in familyMembers"
          :key="member.userId"
          class="member-item"
          :class="{ selected: selectedMembers.includes(member.userId) }"
          @click="toggleMember(member.userId)"
        >
          <div class="member-avatar">
            {{ getMemberInitial(member.userName || "鐢ㄦ埛") }}
          </div>
          <div class="member-info">
            <span class="member-name">{{ member.userName || t("voices.unknown") }}</span>
            <span class="member-role">{{ getRoleText(member.role) }}</span>
          </div>
          <div class="member-check">
            <span v-if="selectedMembers.includes(member.userId)" class="check-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="20 6 9 17 4 12" />
              </svg>
            </span>
          </div>
        </div>
      </div>
    </section>

    <!-- 鏉冮檺璁剧疆 -->
    <section v-if="selectedMembers.length > 0" class="permission-section">
      <h3>{{ t("voices.permissionSetting") }}</h3>
      <div class="permission-options">
        <label class="permission-option" :class="{ active: permission === 'USE' }">
          <input type="radio" v-model="permission" value="USE" />
          <div class="option-content">
            <span class="option-title">{{ t("voices.permissionUse") }}</span>
            <span class="option-desc">{{ t("voices.permissionUseDesc") }}</span>
          </div>
        </label>
        <label class="permission-option" :class="{ active: permission === 'FULL' }">
          <input type="radio" v-model="permission" value="FULL" />
          <div class="option-content">
            <span class="option-title">{{ t("voices.permissionFull") }}</span>
            <span class="option-desc">{{ t("voices.permissionFullDesc") }}</span>
          </div>
        </label>
      </div>
      
      <!-- 杩囨湡鏃堕棿 -->
      <div class="expire-section">
        <label class="expire-label">
          <input type="checkbox" v-model="hasExpire" />
          <span>{{ t("voices.setExpire") }}</span>
        </label>
        <input
          v-if="hasExpire"
          type="date"
          v-model="expireDate"
          class="date-input"
          :min="minDate"
        />
      </div>
    </section>

    <!-- 鎿嶄綔鎸夐挳 -->
    <div class="action-buttons">
      <button class="cancel-btn" @click="handleCancel">
        {{ t("voices.cancel") }}
      </button>
      <button
        class="confirm-btn"
        :disabled="selectedMembers.length === 0 || sharing"
        @click="handleShare"
      >
        <span v-if="sharing">{{ t("voices.sharing") }}</span>
        <span v-else>{{ t("voices.confirmShare", { count: selectedMembers.length }) }}</span>
      </button>
    </div>

    <!-- 宸插垎浜垪琛?-->
    <section v-if="grants.length > 0" class="grants-section">
      <h3>{{ t("voices.sharedList") }}</h3>
      <div class="grants-list">
        <div
          v-for="grant in grants"
          :key="grant.grantId"
          class="grant-item"
        >
          <div class="grant-info">
            <span class="grant-name">{{ grant.granteeName || t("voices.unknown") }}</span>
            <span class="grant-permission">{{ getPermissionText(grant.permission) }}</span>
          </div>
          <div class="grant-actions">
            <span v-if="grant.expiresAt" class="grant-expire">
              {{ t("voices.expireAt", { date: formatDate(grant.expiresAt) }) }}
            </span>
            <button class="revoke-btn" @click="revokeGrant(grant.grantId)">
              {{ t("voices.revoke") }}
            </button>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import { useI18n } from "vue-i18n";
import { createGrant, getGivenGrants, revokeGrant, type CreateGrantRequest, type VoiceGrantDetail, type FamilyMemberDetail } from "../../services/modules/voice.api";
import { checkFamilyRelation, getFamilyMembers, type FamilyMember } from "../../services/modules/family.api";
import { getToken } from "../../utils/token";

const props = defineProps<{
  voiceAssetId: string;
}>();

const emit = defineEmits<{
  (e: "close"): void;
  (e: "success"): void;
}>();

const { t } = useI18n();

const familyLoading = ref(true);
const isInFamily = ref(false);
const familyMembers = ref<(FamilyMember & { userName?: string })[]>([]);
const selectedMembers = ref<string[]>([]);
const permission = ref<"USE" | "FULL">("USE");
const hasExpire = ref(false);
const expireDate = ref("");
const sharing = ref(false);
const grants = ref<VoiceGrantDetail[]>([]);

const minDate = computed(() => {
  const tomorrow = new Date();
  tomorrow.setDate(tomorrow.getDate() + 1);
  return tomorrow.toISOString().split("T")[0];
});

const getMemberInitial = (name: string): string => {
  return name.charAt(0).toUpperCase();
};

const getRoleText = (role: string): string => {
  const map: Record<string, string> = {
    PARENT: t("voices.roleParent"),
    CHILD: t("voices.roleChild"),
    CAREGIVER: t("voices.roleCaregiver"),
    OTHER: t("voices.roleOther"),
  };
  return map[role] || role;
};

const getPermissionText = (perm: string): string => {
  const map: Record<string, string> = {
    USE: t("voices.permissionUse"),
    FULL: t("voices.permissionFull"),
  };
  return map[perm] || perm;
};

const formatDate = (date: string): string => {
  return new Date(date).toLocaleDateString("zh-CN");
};

const toggleMember = (userId: string) => {
  const index = selectedMembers.value.indexOf(userId);
  if (index === -1) {
    selectedMembers.value.push(userId);
  } else {
    selectedMembers.value.splice(index, 1);
  }
};

const handleCancel = () => {
  emit("close");
};

const handleShare = async () => {
  if (selectedMembers.value.length === 0) return;
  
  try {
    sharing.value = true;
    for (const granteeUserId of selectedMembers.value) {
      const request: CreateGrantRequest = {
        voiceAssetId: props.voiceAssetId,
        granteeUserId,
        permission: permission.value,
        expiresAt: hasExpire.value ? expireDate.value : undefined,
      };
      await createGrant(request);
    }
    emit("success");
    await fetchGrants();
    selectedMembers.value = [];
  } catch (error) {
    console.error("鍒嗕韩澶辫触:", error);
    alert(t("voices.shareFailed"));
  } finally {
    sharing.value = false;
  }
};

const revokeGrantById = async (grantId: string) => {
  if (!confirm(t("voices.confirmRevoke"))) return;
  try {
    await revokeGrant(grantId);
    await fetchGrants();
  } catch (error) {
    console.error("鍙栨秷鍒嗕韩澶辫触:", error);
    alert(t("voices.revokeFailed"));
  }
};

const fetchFamilyInfo = async () => {
  try {
    familyLoading.value = true;
    // TODO: 鑾峰彇褰撳墠鐢ㄦ埛淇℃伅
    const currentUserId = "current-user-id"; // 闇€瑕佷粠 store 鑾峰彇
    
    // 鑾峰彇鐢ㄦ埛鎵€灞炲搴?
    const familyResult = await fetch(`/api/family/my`, {
      headers: { Authorization: `Bearer ${getToken()}` }
    }).then(r => r.json());
    
    if (familyResult.code === 200 && familyResult.data?.length > 0) {
      isInFamily.value = true;
      const familyId = familyResult.data[0].familyId;
      const membersResult = await getFamilyMembers(familyId);
      if (membersResult.code === 200 && membersResult.data) {
        familyMembers.value = membersResult.data;
      }
    } else {
      isInFamily.value = false;
    }
  } catch (error) {
    console.error("鑾峰彇瀹跺涵淇℃伅澶辫触:", error);
  } finally {
    familyLoading.value = false;
  }
};

const fetchGrants = async () => {
  try {
    const result = await getGivenGrants();
    if (result.code === 200 && result.data) {
      grants.value = result.data.filter(g => g.voiceAssetId === props.voiceAssetId);
    }
  } catch (error) {
    console.error("鑾峰彇鍒嗕韩鍒楄〃澶辫触:", error);
  }
};

onMounted(() => {
  fetchFamilyInfo();
  fetchGrants();
});
</script>

<style scoped>
.share-voice-page {
  display: grid;
  gap: var(--space-5);
  padding: var(--space-5);
}

.share-tip {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-4);
  background: rgba(251, 191, 36, 0.15);
  border-radius: 12px;
  font-size: 13px;
  color: #92400e;
}

.tip-icon {
  width: 16px;
  height: 16px;
  display: grid;
  place-items: center;
}

.tip-icon svg {
  width: 16px;
  height: 16px;
}

.share-section h3,
.permission-section h3,
.grants-section h3 {
  margin: 0 0 var(--space-4);
  font-family: var(--font-display);
  font-size: 16px;
}

.loading-state {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-4);
  color: var(--color-muted);
  font-size: 14px;
}

.mini-spinner {
  width: 20px;
  height: 20px;
  border: 2px solid rgba(253, 186, 116, 0.2);
  border-top-color: var(--color-accent);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.family-notice,
.empty-members {
  padding: var(--space-5);
  text-align: center;
  background: rgba(253, 186, 116, 0.08);
  border-radius: 14px;
  color: var(--color-muted);
}

.primary-link {
  display: inline-block;
  margin-top: var(--space-3);
  padding: 8px 16px;
  border-radius: 999px;
  background: linear-gradient(135deg, #fb923c, #f97316);
  color: white;
  font-size: 13px;
  font-weight: 600;
  text-decoration: none;
}

.member-list {
  display: grid;
  gap: var(--space-2);
}

.member-item {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3);
  border-radius: 12px;
  border: 1px solid rgba(239, 227, 215, 0.6);
  background: rgba(255, 255, 255, 0.8);
  cursor: pointer;
  transition: all 0.2s ease;
}

.member-item:hover {
  border-color: rgba(229, 139, 58, 0.4);
  background: rgba(253, 186, 116, 0.1);
}

.member-item.selected {
  border-color: #f97316;
  background: rgba(249, 115, 22, 0.1);
}

.member-avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: linear-gradient(135deg, rgba(253, 186, 116, 0.4), rgba(251, 146, 60, 0.3));
  display: grid;
  place-items: center;
  font-weight: 600;
  color: #9a3412;
  flex-shrink: 0;
}

.member-info {
  flex: 1;
  display: grid;
  gap: 2px;
}

.member-name {
  font-weight: 500;
  font-size: 14px;
}

.member-role {
  font-size: 12px;
  color: var(--color-muted);
}

.member-check {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  border: 2px solid rgba(229, 139, 58, 0.3);
  display: grid;
  place-items: center;
}

.member-item.selected .member-check {
  background: #f97316;
  border-color: #f97316;
}

.check-icon {
  color: white;
  width: 14px;
  height: 14px;
  display: grid;
  place-items: center;
}

.check-icon svg {
  width: 14px;
  height: 14px;
}

/* 鏉冮檺璁剧疆 */
.permission-options {
  display: grid;
  gap: var(--space-3);
}

.permission-option {
  display: flex;
  align-items: flex-start;
  gap: var(--space-3);
  padding: var(--space-4);
  border-radius: 14px;
  border: 1px solid rgba(239, 227, 215, 0.6);
  background: rgba(255, 255, 255, 0.8);
  cursor: pointer;
  transition: all 0.2s ease;
}

.permission-option:hover {
  border-color: rgba(229, 139, 58, 0.4);
}

.permission-option.active {
  border-color: #f97316;
  background: rgba(249, 115, 22, 0.08);
}

.permission-option input {
  margin-top: 4px;
}

.option-content {
  display: grid;
  gap: 2px;
}

.option-title {
  font-weight: 500;
  font-size: 14px;
}

.option-desc {
  font-size: 12px;
  color: var(--color-muted);
}

/* 杩囨湡鏃堕棿 */
.expire-section {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  margin-top: var(--space-4);
  padding-top: var(--space-4);
  border-top: 1px solid rgba(239, 227, 215, 0.6);
}

.expire-label {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: 14px;
  cursor: pointer;
}

.date-input {
  padding: 8px 12px;
  border: 1px solid rgba(229, 139, 58, 0.3);
  border-radius: 10px;
  font-size: 14px;
  outline: none;
}

.date-input:focus {
  border-color: #f97316;
}

/* 鎿嶄綔鎸夐挳 */
.action-buttons {
  display: flex;
  gap: var(--space-3);
  padding-top: var(--space-4);
  border-top: 1px solid rgba(239, 227, 215, 0.6);
}

.cancel-btn,
.confirm-btn {
  flex: 1;
  padding: 12px;
  border-radius: 12px;
  font-weight: 600;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.cancel-btn {
  border: 1px solid rgba(229, 139, 58, 0.3);
  background: rgba(255, 255, 255, 0.9);
  color: var(--color-text);
}

.cancel-btn:hover {
  background: rgba(253, 186, 116, 0.1);
}

.confirm-btn {
  border: none;
  background: linear-gradient(135deg, #fb923c, #f97316);
  color: white;
}

.confirm-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* 宸插垎浜垪琛?*/
.grants-section {
  padding-top: var(--space-4);
  border-top: 1px solid rgba(239, 227, 215, 0.6);
}

.grants-list {
  display: grid;
  gap: var(--space-2);
}

.grant-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-3);
  border-radius: 12px;
  background: rgba(253, 186, 116, 0.08);
}

.grant-info {
  display: grid;
  gap: 2px;
}

.grant-name {
  font-weight: 500;
  font-size: 14px;
}

.grant-permission {
  font-size: 12px;
  color: var(--color-muted);
}

.grant-actions {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.grant-expire {
  font-size: 12px;
  color: var(--color-muted);
}

.revoke-btn {
  padding: 6px 12px;
  border-radius: 8px;
  border: 1px solid rgba(248, 113, 113, 0.4);
  background: rgba(248, 113, 113, 0.1);
  color: #b91c1c;
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
}

.revoke-btn:hover {
  background: rgba(248, 113, 113, 0.2);
}
</style>



